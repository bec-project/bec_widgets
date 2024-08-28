(developer.widget_development.tutorial_tests)=

# Testing BEC Widgets

## Importance of Writing Tests for Widgets

Writing tests for widgets, even for simple ones, is crucial in maintaining the reliability and stability of a software
project. Tests help ensure that new contributions don't unintentionally break existing functionality, and they provide a
safety net for developers making changes in the future. In the context of the BEC Widgets, testing is particularly
important due to the complexity of interactions with external systems like the BEC server.

## Testing with Pytest and QtBot

For testing Qt-based applications, we use [`pytest`](https://docs.pytest.org/en/stable/) along with
the [`pytest-qt`](https://pytest-qt.readthedocs.io/en/latest/) plugin, which provides the `qtbot` fixture. `qtbot` is
specifically designed to simplify interactions with Qt applications during testing. It handles the creation, management,
and cleanup of widgets, ensuring that your tests are robust and do not leave behind any lingering resources or open
windows.

## Fixtures for Testing BEC Widgets

Let's break down the key fixtures used in testing BEC Widgets:

1. **`qapplication` Fixture**: This fixture ensures that all Qt applications and widgets are properly closed after each
   test. It uses `qtbot` to wait until all top-level widgets are closed, raising an error if any remain open.

2. **`rpc_register` Fixture**: This fixture manages the `RPCRegister` singleton, ensuring that it is reset after each
   test. This prevents state from leaking between tests, which could cause unexpected behavior.

3. **`bec_dispatcher` Fixture**: This fixture initializes the `BECDispatcher` and ensures that all connections are
   properly disconnected and the BEC client is shut down after each test. Like `rpc_register`, it resets the singleton
   after each test.

4. **`clean_singleton` Fixture**: This fixture cleans up any singleton instances used in error popups, preventing
   interference between tests.

5. **`create_widget` Helper Function**: This function is a helper that should be used in all tests requiring widget
   creation. It ensures that widgets are properly added to `qtbot`, which manages their lifecycle during tests. We
   highly recommend using this function to create widgets in your tests to ensure proper cleanup and compatibility with
   other `autouse` fixtures.

```{note}
These fixtures are automatically applied to all tests within the `tests/unit_tests` directory, ensuring consistency and proper cleanup between tests. You can find all unit test fixtures in the `conftest.py` file located in the `tests/unit_tests` directory of the BEC Widgets repository. 

```

````{dropdown} View code: Conftest with Fixtures
:icon: code-square
:animate: fade-in-slide-down
```{literalinclude} ../../../tests/unit_tests/conftest.py
:language: python
```
````

## Example Test for `PositionerBox`

Below is an example of how to write a simple test for the [`PositionerBox`](user.widgets.positioner_box) widget,
utilizing the fixtures mentioned above:

````{dropdown} View code: PositionerBox Widget Unit Tests
:icon: code-square
:animate: fade-in-slide-down
```{literalinclude} ../../../tests/unit_tests/test_positioner_box.py
:language: python
```
````

## Key Points in the Test:

- **Fixture Use**: The `positioner_box` fixture handles widget creation and mocking of external dependencies. This
  ensures the test runs in isolation and doesn't rely on actual hardware or network connections.

- **Assertion Checks**: The test includes several assertions to verify that the widget initializes correctly, including
  checking the setpoint, precision, and step size.

## Conclusion

By writing tests like the one shown above, you help ensure that your widget behaves as expected. Tests also provide a
way to automatically verify that new changes do not introduce regressions. This is particularly important in a
collaborative environment where multiple developers are contributing to the same codebase. Your tests not only safeguard
your code but also provide confidence to others that their contributions won't break existing functionality.