import os
import re
import time
from pathlib import Path
import questionary as qrt
from core import App
import click

from typing import Union

def positive_int_validation(text: str) -> Union[str, bool]:
    if not text:
        return "Empty string"
    if re.search("[^0-9]", text):
        return "Only numbers (0-9) accepted"
    elif int(text) == 0:
        return "A value of 0 isn't allowed"
    else:
        return True

def positive_int_callback(ctx, param, value):
    try:
        if int(value) <= 0:
            raise click.BadParameter("Should be a strictly positive integer")
    except ValueError:
        raise click.BadParameter("Should be a strictly positive integer")
    return int(value)

def positive_float_validation(text: str, strict: bool = True) -> Union[str, bool]:
    if re.search("[^0-9\.]", text):
        return "Only numbers (0-9) and one dot allowed"
    elif text.count(".") > 1:
        return "Only one dot allowed"
    elif text == "." or not text:
        return "Should be a positive real number"
    elif float(text) == 0 and strict:
        return "A value of 0 isn't allowed"
    else:
        return True

def positive_float_callback(ctx, param, value, strict: bool = True):
    try:
        if float(value) < 0:
            raise click.BadParameter("Should be a positive real number")
        elif float(value) == 0 and strict:
            raise click.BadParameter("0 isn't allowed")
    except ValueError:
        raise click.BadParameter("Should be a positive real number")
    return float(value)

def port_validation(text: str) -> Union[str, bool]:
    if not text:
        return "Empty string"
    if re.search("[^0-9]", text):
        return "Only numbers (0-9) accepted"
    elif int(text) < 1 or int(text) > 4:
        return "Value must be between 1 and 4"
    else:
        return True

def port_callback(ctx, param, value):
    try:
        if int(value) < 1 or int(value) > 4:
            raise click.BadParameter("Should be an integer between 1 and 4")
    except ValueError:
        raise click.BadParameter("Should be an integer between 1 and 4")
    return int(value)


@click.group(help="Captures USB traffic from a Gamecube controller adapter, and converts its data into a human readable format")
def cli():
    pass

@cli.command(help="Enter capture configuration through an interactive prompt in the terminal")
@click.option(
    "--verbose", "-v", "arg_verbose", default=False, count=True, help="Log verbosity level"
)
def interactive_prompt(arg_verbose):

    user_input = qrt.text("Enter bus number : ", validate=positive_int_validation).ask()
    if not user_input:
        exit(1)
    bus_number: int = int(user_input)

    user_input: str = qrt.text("Enter device number : ", validate=positive_int_validation).ask()
    if not user_input:
        exit(2)
    device_number: int = int(user_input)

    user_input = qrt.text("Enter player port number : ", validate = port_validation).ask()
    if not user_input:
        exit(3)
    player_port: int = int(user_input)

    user_input = qrt.text("Enter name of output file : ").ask()
    if not user_input:
        exit(4)
    output_file: str = user_input

    user_input = qrt.text("Enter capture duration (seconds) : ", validate=lambda x: positive_float_validation(x, True)).ask()
    if not user_input:
        exit(5)
    duration: float = float(user_input)

    user_input = qrt.text("Enter time until capture start (seconds) : ", validate=lambda x: positive_float_validation(x, False)).ask()
    if not user_input:
        exit(6)
    wait_time: float = float(user_input)

    if not Path(f"/dev/usbmon{bus_number}").exists():
        print(f"usbmon pipe for bus number {bus_number} \"/dev/usbmon{bus_number}\" can't be found. Have you activated usbmon?")
        exit(7)
    if wait_time > 0:
        print("Starting soon...")
        time.sleep(wait_time)

    app: App = App(device_number, bus_number, player_port, output_file, duration)
    app.main(arg_verbose)

@cli.command(help="Pass capture configuration through flags")
@click.option(
    "--verbose", "-v", "arg_verbose", required=False, default=False, count=True, help="Log verbosity level"
)
@click.option(
    "--bus", "-b", "arg_bus", required=True, type=int, callback=positive_int_callback, help="USB bus number to watch"
)
@click.option(
    "--device", "-d", "arg_device", required=True, type=int, callback=positive_int_callback, help="Device number to extract data from"
)
@click.option(
    "--port", "-p", "arg_port", required=True, type=int, callback=port_callback, help="Adapter port number to watch"
)
@click.option(
    "--output", "-o", "arg_output", required=True, help="Location of output file"
)
@click.option(
    "--capture-time", "-c", "arg_capture_time", required=True, type=float, callback=lambda ctx, param, value: positive_float_callback(ctx, param, value, True), help="Duration of packet capture"
)
@click.option(
    "--wait-time", "-w", "arg_wait_time", required=False, type=float, default=0.0, callback=lambda ctx, param, value: positive_float_callback(ctx, param, value, False), help="Wait time before starting capture"
)
def flag_command(arg_verbose, arg_bus, arg_device, arg_port, arg_output, arg_capture_time, arg_wait_time):
    if not Path(f"/dev/usbmon{arg_bus}").exists():
        print(f"usbmon pipe for bus number {arg_bus} \"/dev/usbmon{arg_bus}\" can't be found. Have you activated usbmon?")
        exit(7)
    if arg_wait_time > 0:
        print("Starting soon...")
        time.sleep(arg_wait_time)

    app: App = App(arg_device, arg_bus, arg_port, arg_output, arg_capture_time)
    app.main(arg_verbose)
