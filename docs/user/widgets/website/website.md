(user.widgets.website)=

# Website Widget

````{tab} Overview

The [`Website Widget`](/api_reference/_autosummary/bec_widgets.cli.client.WebsiteWidget) is a versatile tool that allows users to display websites directly within the BEC GUI. This widget is useful for embedding documentation, dashboards, or any web-based tools within the application interface. It is designed to be integrated within a [`BECDockArea`](user.widgets.bec_dock_area) or used as an individual component in your application through `BEC Designer`.

## Key Features:
- **URL Display**: Set and display any website URL within the widget.
- **Navigation Controls**: Navigate through the website’s history with back and forward controls.
- **Reload Functionality**: Reload the currently displayed website to ensure up-to-date content.

````

````{tab} Examples - CLI

The `WebsiteWidget` can be embedded within a [`BECDockArea`](user.widgets.bec_dock_area) or used as an individual component in your application through `BEC Designer`. The following examples demonstrate how to create and use the `WebsiteWidget` in different scenarios.

## Example 1 - Adding Website Widget to BECDockArea

In this example, we demonstrate how to add a `WebsiteWidget` to a `BECDockArea` and set the URL of the website to be displayed.

```python
# Add a new dock with a WebsiteWidget
dock_area = gui.new()
web = dock_area.new().new(gui.available_widgets.WebsiteWidget)

# Set the URL of the website to display
web.set_url("https://bec.readthedocs.io/en/latest/")
```

## Example 2 - Navigating within the Website Widget

The `WebsiteWidget` allows users to navigate back and forward through the website’s history. This example shows how to implement these navigation controls.
If you click on a link in the website, you can use the back and forward buttons to navigate through the history.

```python
# Go back in the website history
web.back()

# Go forward in the website history
web.forward()
```

## Example 3 - Reloading the Website

To ensure that the displayed website content is up-to-date, you can use the reload functionality.

```python
# Reload the current website
web.reload()
```

## Example 4 - Retrieving the Current URL

You may want to retrieve the current URL being displayed in the `WebsiteWidget`. The following example demonstrates how to access the current URL.

```python
# Get the current URL of the WebsiteWidget
current_url = web.get_url()
print(f"The current URL is: {current_url}")
```

````

````{tab} API
```{eval-rst} 
.. include:: /api_reference/_autosummary/bec_widgets.cli.client.WebsiteWidget.rst
```
````
