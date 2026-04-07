from bec_widgets.widgets.utility.bec_term.protocol import BecTerminal
from bec_widgets.widgets.utility.bec_term.qtermwidget_wrapper import BecQTerm


def get_current_bec_term_class() -> type[BecTerminal]:
    return BecQTerm
