"""The sequencer GUI concepts, in the order they are shown."""

from bec_widgets.widgets.control.sequencer.blocks.blocks_editor import BlocksEditor
from bec_widgets.widgets.control.sequencer.flow.flow_editor import FlowEditor
from bec_widgets.widgets.control.sequencer.guided.guided_editor import GuidedEditor
from bec_widgets.widgets.control.sequencer.recipe.recipe_editor import RecipeEditor
from bec_widgets.widgets.control.sequencer.table.table_editor import TableEditor

CONCEPTS = {
    cls.CONCEPT_ID: cls
    for cls in (RecipeEditor, BlocksEditor, TableEditor, GuidedEditor, FlowEditor)
}
