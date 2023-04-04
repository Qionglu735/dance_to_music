
import asyncio
import importlib
import logging
import math
import sys
import threading
import traceback

import keyboard
import numpy as np
import sounddevice as sd

buttplug = importlib.import_module("buttplug-py.buttplug")
Client = buttplug.Client
ProtocolSpec = buttplug.ProtocolSpec
WebsocketConnector = buttplug.WebsocketConnector

threshold = 0.4
threshold_adj = 0.6
norm_size = 100
norm_size_adj = 8


class SoundThread(threading.Thread):
    def __init__(self):
        super(SoundThread, self).__init__()
        self._stop_event = threading.Event()
        self.volume_norm = 0

    def print_sound(self, indata, outdata, frames, time, status):
        self.volume_norm = np.linalg.norm(indata)
        # print(f"{volume_norm}")

    def run(self):
        # print(sd.query_devices())
        _out, _in = -1, -1
        device_list = sd.query_devices()
        for i in device_list:
            # print(i)
            # if _out < 0 and "CABLE Output (VB-Audio Virtual" in i["name"]:
            if _out < 0 and "VoiceMeeter Output (VB-Audio VoiceMeeter VAIO)" in i["name"]:
                print(i["index"], i["name"])
                _out = i["index"]
            if _in < 0 and "VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)" in i["name"]:
                print(i["index"], i["name"])
                _in = i["index"]
        if _out == -1 or _in == -1:
            print("VB-Audio Not Found")
            return

        while not self._stop_event.is_set():
            with sd.Stream(device=[_out, _in], callback=self.print_sound):
                sd.sleep(100)

    def stop(self):
        self._stop_event.set()


sound_thread = SoundThread()


async def main():

    global sound_thread
    sound_thread.start()

    global threshold

    norm_list = list()
    while sound_thread.is_alive():
        try:
            client = Client("Music Vibrator", ProtocolSpec.v3)
            connector = WebsocketConnector("ws://127.0.0.1:12345", logger=client.logger)
            await client.connect(connector)

        except Exception:
            print("Exception: client.connect()")
            traceback.print_exc()
            continue

        await client.start_scanning()
        print("Scanning ...")
        await asyncio.sleep(3)

        print(f"Devices: {client.devices}")
        if len(client.devices) == 0:
            await client.stop_scanning()
            await asyncio.sleep(3)
            await client.disconnect()
            await asyncio.sleep(3)
            continue

        device_index = -1
        for i in client.devices:
            # print(client.devices[i].__dict__)
            if "Roselex" in client.devices[i].name:
                device_index = i
        if device_index == -1:
            await client.stop_scanning()
            await asyncio.sleep(3)
            await client.disconnect()
            await asyncio.sleep(3)
            continue

        for i in [
            (1.0, 0.1, ),
            (0, 0.1, ),
            (1.0, 0.1, ),
            (0, 0.1, ),
            (1.0, 0.1, ),
            (0, 0.1, ),
        ]:
            await client.devices[device_index].actuators[0].command(i[0])
            await asyncio.sleep(i[1])
        while sound_thread.is_alive():
            volume_norm = sound_thread.volume_norm

            if len(norm_list) >= norm_size * norm_size_adj:
                norm_list = norm_list[len(norm_list) - norm_size * norm_size_adj + 1:]
            if volume_norm >= 0.1:
                norm_list.append(volume_norm)
            if len(norm_list) == 0:
                # print("len(norm_list) == 0 continue")
                continue

            threshold = max(0.1, round(sum(norm_list) / len(norm_list) * 2 * threshold_adj, 2))
            vibrate = float(1 - 1 / (max(volume_norm - threshold, 0) + 1))

            sys.stdout.write(
                f"\r"
                f"Volume: {round(float(volume_norm), 2)}/{threshold}({threshold_adj}) "
                f"Vibrate: {round(vibrate, 2)} "
                f"Sample: {len(norm_list)}/{norm_size * norm_size_adj} "
                # f"Vibrate: {round((volume_norm - threshold) / (max(norm_list) + 0.01 - threshold), 2)} "
                # f"{round(sum(norm_list), 2)}/{len(norm_list)}={round(sum(norm_list) / len(norm_list), 2)}"
            )
            try:
                await client.devices[device_index].actuators[0].command(min(1.0, vibrate))
            except Exception:
                print("Exception: actuators.command()")
                traceback.print_exc()
                break

        await client.disconnect()
        await asyncio.sleep(3)

    sound_thread.join()


def keyboard_handler(event):
    global threshold_adj
    global norm_size_adj
    if event.name in ["up", "w"]:
        threshold_adj = min(2.0, round(threshold_adj + 0.01, 2))
        # print(threshold)
    elif event.name in ["down", "s"]:
        threshold_adj = max(-2.0, round(threshold_adj - 0.01, 2))
        # print(threshold)
    elif event.name in ["left", "a"]:
        norm_size_adj = max(1, math.floor(norm_size_adj / 2))
        # print(threshold)
    elif event.name in ["right", "d"]:
        norm_size_adj = norm_size_adj * 2
        # print(threshold)
    elif event.name in ["esc"]:
        global sound_thread
        sound_thread.stop()


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    keyboard.on_press(lambda event: keyboard_handler(event))
    asyncio.run(main(), debug=True)
