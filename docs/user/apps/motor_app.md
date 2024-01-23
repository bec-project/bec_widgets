(user.apps.motor_app)=
# Motor Alignment

The Motor Alignment Application is a key component of the BEC Widgets suite, designed to facilitate precise alignment of motors. 
Users can easily launch this app using the script located at  `/bec_widgets/example/motor_movement/motor_example.py` script. 
The application's primary function is to enable users to align motors to specific positions and to visually track the motor's trajectory.

## Controlling Motors

In the top middle panel of the application, users will find combobox dropdown menus for selecting the motors they wish to track on the x and y axes of the motor map. 
These motors are automatically loaded from the current active BEC instance, ensuring seamless integration and ease of use.

There are two primary methods to control motor movements:


1. **Manual Control with Arrow Keys:** Users can manually drive the motors using arrow keys. Before doing so, they need to select the step size for each motor, allowing for precise and incremental movements.
2. **Direct Position Entry:** Alternatively, users can input a desired position in the text input box and then click the Go button. This action will move the motor directly to the specified coordinates.

As the motors are moved, their trajectory is plotted in real-time, providing users with a visual representation of the motor's path. This feature is particularly useful for understanding the movement patterns and making necessary adjustments.


## Saving and Exporting Data

Users have the ability to save the current motor position in a table widget. This functionality is beneficial for recalling and returning to specific positions. By clicking the Go button in the table widget, the motors will automatically move back to the saved position.

Additionally, users can annotate each saved position with notes and comments directly in the table widget. This feature is invaluable for keeping track of specific alignment settings or observations. The contents of the table, including the notes, can be exported to a .csv file. This exported data can be used for initiating scans or for record-keeping purposes.

The table widget also supports saving and loading functionalities, allowing users to preserve their motor positions and notes across sessions. The saved files are in a user-friendly format for ease of access and use.


## Example of Use

![Motor app example](motor_app_10fps.gif)

