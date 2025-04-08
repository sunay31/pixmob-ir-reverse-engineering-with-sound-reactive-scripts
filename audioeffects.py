import serial
import time
import numpy as np
import sounddevice as sd
import collections
import random
import datetime
from pixmob_conversion_funcs import bits_to_arduino_string
from effect_definitions import base_color_effects, tail_codes, special_effects
import config as cfg

EXTERNAL_MIC_INDEX = None # Change this to the index of your external microphone 

# Sound parameters
SAMPLE_RATE = 44100  # Sampling rate in Hz
BLOCK_SIZE = 1024  # Number of samples per read
SOUND_THRESHOLD_LOW = 0.05  # Ignore sounds below this level (reduce sensitivity)
SOUND_THRESHOLD_HIGH = 0.2  # Upper threshold for max effect
MOVING_AVERAGE_WINDOW = 5  # Number of past sound levels to average

# Queue to store past sound levels
sound_history = collections.deque(maxlen=MOVING_AVERAGE_WINDOW)

# Effect cooldown time to prevent rapid flickering
EFFECT_CHANGE_DELAY = 0.2   # Seconds between color changes
last_effect_time = time.time()

# **Grouped color effects per threshold (Randomized)**
EFFECTS_TO_SHOW = {
    "low": [
        {"main_effect": "RED", "tail_code": None},
        {"main_effect": "ORANGE", "tail_code": None}
    ],
    "medium": [
        {"main_effect": "GREEN", "tail_code": None},
        {"main_effect": "TURQUOISE", "tail_code": None}
    ],
    "high": [
        {"main_effect": "BLUE", "tail_code": None},
        {"main_effect": "MAGENTA", "tail_code": None}
    ],
    "very_high": [
        {"main_effect": "PINK", "tail_code": None},
        {"main_effect": "WHITISH", "tail_code": None}
    ]
}

# Setup Arduino connection
arduino = serial.Serial(port=cfg.ARDUINO_SERIAL_PORT, baudrate=cfg.ARDUINO_BAUD_RATE, timeout=.1)
time.sleep(2.5)

def send_effect(main_effect, tail_code):
    """Sends a light effect command to the Arduino."""
    if main_effect in base_color_effects:
        effect_bits = base_color_effects[main_effect]
        if tail_code:
            effect_bits += tail_codes.get(tail_code, "")
    elif main_effect in special_effects:
        effect_bits = special_effects[main_effect]
        if tail_code:
            print(f"Tail code '{tail_code}' ignored for special effect '{main_effect}'")
    else:
        print(f"Invalid effect: {main_effect}")
        return
    
    arduino_string = bits_to_arduino_string(effect_bits)
    arduino.write(bytes(arduino_string, 'utf-8'))
    print(f"Sent effect: {main_effect}, {'no tail' if not tail_code else 'tail: ' + tail_code}")

def get_effect_for_sound_level(volume_norm):
    """Randomly selects an effect from the assigned threshold range."""
    if volume_norm < SOUND_THRESHOLD_LOW:
        return None  # Ignore very low sounds
    elif volume_norm < 0.1:
        return random.choice(EFFECTS_TO_SHOW["low"])  # Randomized between RED & ORANGE
    elif volume_norm < 0.15:
        return random.choice(EFFECTS_TO_SHOW["medium"])  # Randomized between GREEN & TURQUOISE
    elif volume_norm < 0.18:
        return random.choice(EFFECTS_TO_SHOW["high"])  # Randomized between BLUE & MAGENTA
    else:
        return random.choice(EFFECTS_TO_SHOW["very_high"])  # Randomized between PINK & WHITISH

def audio_callback(indata, frames, callback_time, status):
    """Processes real-time audio input and triggers effects based on smoothed sound level."""
    global last_effect_time

    # Compute current sound level
    volume_norm = np.linalg.norm(indata) / np.sqrt(len(indata))

    # Update moving average
    sound_history.append(volume_norm)
    smoothed_volume = np.mean(sound_history)

    # Get corresponding effect
    effect_instance = get_effect_for_sound_level(smoothed_volume)

    # Prevent rapid effect switching
    if effect_instance and (time.time() - last_effect_time) > EFFECT_CHANGE_DELAY:
        send_effect(effect_instance["main_effect"], effect_instance.get("tail_code", None))
        last_effect_time = time.time()

# Start listening to the microphone
print("Available Audio Devices:")
print(sd.query_devices())  # List all devices for reference
print(f"\n Using External Microphone (Index {EXTERNAL_MIC_INDEX})")

with sd.InputStream(
    device=EXTERNAL_MIC_INDEX, 
    callback=audio_callback,
    channels=1, #Change this to 2 if you want stereo input, varies on the type of microphone used
    samplerate=SAMPLE_RATE,
    blocksize=BLOCK_SIZE
):
    print("Listening for sound... Press Ctrl+C to stop.")
    while True:
        time.sleep(0.1)
