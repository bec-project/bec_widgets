import threading


class ThreadTracker:
    def __init__(self, exclude_names=None):
        self.exclude_names = exclude_names if exclude_names else []
        self.initial_threads = self._capture_threads()

    def _capture_threads(self):
        return set(
            th
            for th in threading.enumerate()
            if not any(ex_name in th.name for ex_name in self.exclude_names)
            and th is not threading.main_thread()
        )

    def _thread_info(self, threads):
        return ", \n".join(f"{th.name}(ID: {th.ident})" for th in threads)

    def check_unfinished_threads(self):
        current_threads = self._capture_threads()
        additional_threads = current_threads - self.initial_threads
        closed_threads = self.initial_threads - current_threads
        if additional_threads:
            raise Exception(
                f"###### Initial threads ######:\n {self._thread_info(self.initial_threads)}\n"
                f"###### Current threads ######:\n {self._thread_info(current_threads)}\n"
                f"###### Closed threads ######:\n {self._thread_info(closed_threads)}\n"
                f"###### Unfinished threads ######:\n {self._thread_info(additional_threads)}"
            )
        else:
            print(
                "All threads properly closed.\n"
                f"###### Initial threads ######:\n {self._thread_info(self.initial_threads)}\n"
                f"###### Current threads ######:\n {self._thread_info(current_threads)}\n"
                f"###### Closed threads ######:\n {self._thread_info(closed_threads)}"
            )
