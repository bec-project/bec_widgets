import webbrowser


class BECWebLinksMixin:
    @staticmethod
    def open_bec_docs():
        webbrowser.open("https://beamline-experiment-control.readthedocs.io/en/latest/")

    @staticmethod
    def open_bec_widgets_docs():
        webbrowser.open("https://bec.readthedocs.io/projects/bec-widgets/en/latest/")

    @staticmethod
    def open_bec_bug_report():
        webbrowser.open("https://gitlab.psi.ch/groups/bec/-/issues/")
