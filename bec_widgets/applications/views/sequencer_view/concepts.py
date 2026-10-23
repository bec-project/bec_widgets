"""The sequencer GUI concepts, in the order they are shown."""

from bec_widgets.widgets.control.sequencer.recipe.recipe_editor import RecipeEditor

CONCEPTS = {cls.CONCEPT_ID: cls for cls in (RecipeEditor,)}
