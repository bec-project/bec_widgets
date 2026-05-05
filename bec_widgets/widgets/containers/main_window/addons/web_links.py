import webbrowser


class BECWebLinksMixin:
    @staticmethod
    def open_bec_docs():
        webbrowser.open("https://bec-project.github.io/bec_docs/")

    @staticmethod
    def open_bec_bug_report():
        webbrowser.open("https://github.com/bec-project/bec_widgets/issues")
