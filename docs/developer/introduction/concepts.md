(developer.concepts)=
# Concepts
This section provides an overview of the core concepts of BEC Widgets, which are based on the single-responsibility principle and modular design.

## Moduler Design
We develop widgets with the single-responsibility principle in mind, meaning each widget is designed for a specific task. Our goal is to keep widgets simple, using them primarily for visualization or to initiate actions within BEC. Following these ideas, widgets should be designed to be reusable in various applications, making them versatile building blocks for larger GUIs. 

We offer up to three different options for composing larger GUIs from these modular widgets: BEC Designer, DockArea widget, or scripting from the command line interface. More information about these options can be found in the user sections on [applications](user.applications).

## Client-Server Architecture

BEC Widgets is built on top of the [BEC](https://bec.readthedocs.io/en/latest/) package, which provides the backend for beamline experiment control. BEC Widgets is a client of BEC, meaning it can interact with the backend through a client-server architecture. To make full usage of the available features of BEC, we recommend to check the documentation about [data access](https://bec.readthedocs.io/en/latest/developer/data_access/data_access.html) in which the messaging and event system of BEC is described.
In the context of BEC Widgets, the [`BECDispatcher`](/api_reference/_autosummary/bec_widgets.utils.bec_dispatcher.BECDispatcher) connects to this messaging and event system, allowing you to link your Qt [`Slots`](https://www.pythonguis.com/tutorials/pyside6-signals-slots-events/) to messages and event received from BEC.

