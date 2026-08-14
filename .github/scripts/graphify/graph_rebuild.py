"""Build the graphify knowledge graph for this repository (CI-friendly, headless).

Usage: python graph_rebuild.py <repo_root> <spec.json>

The spec lists code roots with their scan roots (paths relative to <repo_root>):
    {"code_roots": [{"files": "bec_lib/bec_lib", "root": "bec_lib"}, ...]}
Scan roots control node-id relativization so that import ids resolve (e.g. the
``bec_lib.endpoints`` import matches the ``bec_lib_endpoints`` file stem). Roots are
processed in order; each file is claimed by the first root that matches, so package
roots must come before the repo-wide catch-all.

AST extraction is deterministic and needs no LLM. The semantic layer (docs, diagrams)
is merged from graphify-out/cache/semantic when present (e.g. restored from a CI
cache); otherwise the build is code-only and a note is printed.

The build writes ``graphify-out/build_meta.json``, which identifies *which* state of the
repository the graph describes. ``version`` — the released package version the graph was
built from — is the key consumers compare against their installed package to decide
whether their local copy is stale. ``requires`` records the BEC-family constraints in
force at build time, so a graph built for one bec_lib range can be spotted as mismatched
against a very different installed one. GITHUB_* environment variables fill in the
release identity in CI; locally those fields stay null.
"""

import json
import os
import sys
import tomllib
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version
from pathlib import Path

# Dependencies whose version the graph is meaningfully coupled to: a graph of this
# repository describes code that calls into these, so a large drift in them dates it.
BEC_FAMILY = ("bec_lib", "bec_ipython_client", "bec_widgets", "ophyd_devices", "bec_qthemes")


def _projects(repo: Path, spec: dict) -> list[dict]:
    """Load the [project] table of every pyproject.toml this repository releases.

    ``version_from`` is one path or a list of them, relative to the repo root. A
    monorepo lists each distribution it ships (bec releases four from one tree); a
    single-package repo can leave it out and get the root pyproject.toml.
    """
    rels = spec.get("version_from", "pyproject.toml")
    rels = [rels] if isinstance(rels, str) else rels
    projects = []
    for rel in rels:
        path = repo / rel
        if not path.is_file():
            print(f"  note: {rel} not found - it contributes no version to build_meta")
            continue
        project = tomllib.loads(path.read_text(encoding="utf-8")).get("project", {})
        if project.get("name"):
            projects.append(project)
    if not projects:
        print("  note: no pyproject.toml found - build_meta version will be null")
    return projects


def _build_identity(repo: Path, spec: dict, graph) -> dict:
    """Assemble the identity block that consumers use for staleness checks."""
    projects = _projects(repo, spec)
    # every distribution built from this tree, so a monorepo stamps all of them rather
    # than silently speaking for one; packages released together share a version
    packages = {p["name"]: p.get("version") for p in projects}
    # only constraints on BEC-family packages released from *other* repositories; these
    # are floors ("bec_lib~=3.134"), not the version that was resolved at build time
    requires = {
        name: req
        for p in projects
        for req in p.get("dependencies", [])
        for name in BEC_FAMILY
        if req.replace("-", "_").startswith(name) and name not in packages
    }
    try:
        graphify_version = _dist_version("graphifyy")
    except PackageNotFoundError:
        graphify_version = None

    tag = os.environ.get("GRAPH_RELEASE_TAG") or None
    return {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "package": projects[0]["name"] if projects else None,
        # the staleness key; co-released packages share it, so the first is the repo's
        "version": projects[0].get("version") if projects else None,
        "packages": packages,
        "tag": tag,
        "release": bool(tag),
        # the exact revision the graph describes - the precise check when a checkout
        # sits ahead of the last release and versions alone cannot separate them
        "commit": os.environ.get("GITHUB_SHA") or None,
        "repository": os.environ.get("GITHUB_REPOSITORY") or None,
        "graphify_version": graphify_version,
        "requires": requires,
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
    }


def main() -> None:
    repo = Path(sys.argv[1]).resolve()
    spec = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    os.chdir(repo)

    from graphify.analyze import god_nodes, suggest_questions, surprising_connections
    from graphify.build import build_from_json
    from graphify.cache import check_semantic_cache
    from graphify.cluster import cluster, score_all
    from graphify.detect import detect, save_manifest
    from graphify.diagnostics import diagnose_extraction
    from graphify.export import to_json
    from graphify.extract import extract
    from graphify.report import generate

    out = Path("graphify-out")
    out.mkdir(exist_ok=True)

    detection = detect(repo)
    # drop any stray literal-~ directories (unexpanded-tilde artifacts)
    for cat in list(detection.get("files", {})):
        detection["files"][cat] = [f for f in detection["files"][cat] if "/~/" not in f]

    all_nodes, all_edges, all_hyper = [], [], []
    seen_ids: set[str] = set()
    claimed: set[str] = set()
    detected_code = [f for f in detection["files"].get("code", [])]
    for code_root in spec["code_roots"]:
        files_dir = (repo / code_root["files"]).resolve()
        croot = (repo / code_root["root"]).resolve()
        prefix = str(files_dir) + "/"
        files = [Path(f) for f in detected_code if f.startswith(prefix) and f not in claimed]
        claimed.update(str(f) for f in files)
        if not files:
            print(f"  {code_root['files']}: no files, skipped")
            continue
        res = extract(files, cache_root=croot)
        for node in res["nodes"]:
            if node["id"] not in seen_ids:
                seen_ids.add(node["id"])
                all_nodes.append(node)
        all_edges += res["edges"]
        print(
            f"  {code_root['files']} (root={code_root['root']}): "
            f"{len(res['nodes'])} nodes, {len(res['edges'])} edges"
        )

    doc_files = [
        f for cat in ("document", "paper", "image") for f in detection["files"].get(cat, [])
    ]
    c_nodes, c_edges, c_hyper, uncached = check_semantic_cache(doc_files, root=str(repo))
    for node in c_nodes:
        if node["id"] not in seen_ids:
            seen_ids.add(node["id"])
            all_nodes.append(node)
    all_edges += c_edges
    all_hyper += c_hyper
    if uncached:
        print(
            f"  note: {len(uncached)}/{len(doc_files)} docs have no cached semantic layer "
            "(code-only build for those files; refresh the semantic layer locally)"
        )

    extraction = {
        "nodes": all_nodes,
        "edges": all_edges,
        "hyperedges": all_hyper,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    print(f"extraction: {len(all_nodes)} nodes, {len(all_edges)} edges")

    graph = build_from_json(extraction, root=str(repo), directed=True)
    if graph.number_of_nodes() == 0:
        raise SystemExit("ERROR: extraction produced an empty graph")
    communities = cluster(graph)
    cohesion = score_all(graph, communities)
    gods = god_nodes(graph)
    surprises = surprising_connections(graph, communities)
    # keep any labels from a previous (cached) run; new communities get placeholders
    labels_path = out / ".graphify_labels.json"
    prior = json.loads(labels_path.read_text(encoding="utf-8")) if labels_path.exists() else {}
    labels = {cid: prior.get(str(cid), f"Community {cid}") for cid in communities}
    questions = suggest_questions(graph, communities, labels)

    (out / "graph.json").unlink(missing_ok=True)
    if not to_json(graph, communities, "graphify-out/graph.json"):
        raise SystemExit("ERROR: graph.json was not written")
    report = generate(
        graph,
        communities,
        cohesion,
        labels,
        gods,
        surprises,
        detection,
        {"input": 0, "output": 0},
        str(repo),
        suggested_questions=questions,
    )
    (out / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    labels_path.write_text(
        json.dumps({str(k): v for k, v in labels.items()}, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges, "
        f"{len(communities)} communities (directed)"
    )

    summary = diagnose_extraction(extraction, directed=True, root=str(repo))
    print(
        "health:",
        {
            k: summary.get(k, 0)
            for k in ("dangling_endpoint_edges", "missing_endpoint_edges", "self_loop_edges")
        },
    )

    save_manifest(detection.get("all_files") or detection["files"], root=str(repo))
    meta = _build_identity(repo, spec, graph)
    (out / "build_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Embed the same identity inside the map. build_meta.json alone is not enough: a
    # graph.json routinely gets copied around on its own, and an unlabelled map that
    # cannot say which release it describes cannot be trusted for anything.
    graph_doc = json.loads((out / "graph.json").read_text(encoding="utf-8"))
    graph_doc["build_meta"] = meta
    (out / "graph.json").write_text(json.dumps(graph_doc), encoding="utf-8")

    print(f"meta: {meta['package']} {meta['version']} (tag={meta['tag']})")


if __name__ == "__main__":
    main()
