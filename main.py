from gpiozero import Button
import time

# Define the GPIO pins used for input buttons
button_pins = [16, 5, 13, 6, 26, 19, 21, 20, 15, 12, 14, 23]

# Create Button instances for each pin, enabling pull-up resistors
buttons = [Button(pin, pull_up=True) for pin in button_pins]

try:
    while True:
        for button in buttons:
            # Check if the button is pressed
            if button.is_pressed:
                print(f"Button {button.pin} is pressed!")
            # Optionally, you can print a message if the button is not pressed:
            # else:
            #     print(f"Button {button.pin} is not pressed!")
            
        # Add a short delay to avoid excessive button state checks
        time.sleep(0.1)

except KeyboardInterrupt:
    print("Program interrupted by the user")
