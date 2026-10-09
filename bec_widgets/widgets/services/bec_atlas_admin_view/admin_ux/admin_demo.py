"""Demo data for the reworked admin view, used by its tests and screenshots.

Beamtimes are placed relative to today, so "next" and "past" stay meaningful.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from bec_lib.messages import (
    DeploymentInfoMessage,
    ExperimentInfoMessage,
    MessagingConfig,
    MessagingServiceScopeConfig,
    SessionInfoMessage,
)

_PEOPLE = {
    "p22622": ("Jane", "Smith", "In-situ SAXS of lipid nanoparticle self-assembly", -2, 3),
    "p22623": ("Marco", "Rossi", "Time-resolved WAXS on cycling battery cathodes", 3, 3),
    "p22631": ("Aiko", "Tanaka", "Ptychographic X-ray tomography of trabecular bone", 11, 4),
    "p22652": ("Lena", "Fischer", "Coherent diffraction imaging of strained nanocrystals", 33, 2),
    "p22604": ("Klaus", "Weber", "Detector distance calibration and flat-field update", -24, 1),
    "p22640": ("Beamline", "Staff", "Staff test and alignment account", None, None),
}


def _schedule(start_offset: int | None, length: int | None, now: datetime) -> list[dict]:
    if start_offset is None:
        return []
    start = (now + timedelta(days=start_offset)).replace(hour=8, minute=0, second=0)
    end = (start + timedelta(days=length)).replace(hour=8)
    fmt = "%d/%m/%Y %H:%M:%S"
    return [{"start": start.strftime(fmt), "end": end.strftime(fmt)}]


def demo_experiments(realm: str = "X12SA", now: datetime | None = None) -> list[dict]:
    """Experiments of one realm as BEC Atlas lists them."""
    now = now or datetime.now()
    infos = []
    for pgroup, (first, last, title, offset, length) in _PEOPLE.items():
        number = pgroup[1:]
        infos.append(
            ExperimentInfoMessage(
                realm_id=realm,
                proposal="" if pgroup == "p22640" else f"2026{number}",
                title=title,
                firstname=first,
                lastname=last,
                email=f"{first.lower()}.{last.lower()}@psi.ch",
                account=f"{last.lower()}_{first[0].lower()}",
                pi_firstname=first,
                pi_lastname=last,
                pi_email=f"{first.lower()}.{last.lower()}@psi.ch",
                pi_account=f"{last.lower()}_{first[0].lower()}",
                eaccount=f"e{number}",
                pgroup=pgroup,
                abstract=(
                    f"{title}. The group combines scanning and full-field measurements to follow "
                    "structural changes in situ, with automated data reduction during the beamtime."
                ),
                schedule=_schedule(offset, length, now),
            ).model_dump()
        )
    return infos


def demo_deployment(active_pgroup: str = "p22622", realm: str = "X12SA") -> DeploymentInfoMessage:
    """Deployment info with ``active_pgroup`` as the active experiment."""
    experiment = next(e for e in demo_experiments(realm) if e["pgroup"] == active_pgroup)
    scope = MessagingServiceScopeConfig(enabled=False)
    return DeploymentInfoMessage(
        deployment_id="dep-x12sa",
        name="cSAXS",
        active_session=SessionInfoMessage(
            name="default", experiment=ExperimentInfoMessage.model_validate(experiment)
        ),
        messaging_config=MessagingConfig(signal=scope, teams=scope, scilog=scope),
    )
