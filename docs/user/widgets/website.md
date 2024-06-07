(user.widgets.website)=
# [Website Widget](/api_reference/_autosummary/bec_widgets.cli.client.WebsiteWidget)
**Purpose:**

The Website Widget is a widget that allows you to display a website within the BEC GUI. The widget can be used to display any website. 

**Key Features:**

- set the URL of the website to display.
- reload the website.
- navigate back and forward in the website history.

**Code example:**

The following code snipped demonstrates how to create a `WebsiteWidget` using BEC Widgets within BEC.
```python
# adds a new dock with a website widget
web = gui.add_dock().add_widget("Website")
# set the URL of the website to display
web.set_url("https://bec.readthedocs.io/en/latest/")
```