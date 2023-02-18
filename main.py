
import asyncio
import importlib
import logging
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
threshold_adj = 0.0


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
        for i in sd.query_devices():
            if _out < 0 and "CABLE Output (VB-Audio Virtual" in i["name"]:
                print(i)
                _out = i["index"]
            if _in < 0 and "CABLE Input (VB-Audio Virtual" in i["name"]:
                print(i)
                _in = i["index"]
        while not self._stop_event.is_set():
            with sd.Stream(device=[_out, _in], callback=self.print_sound):
                sd.sleep(100)

    def stop(self):
        self._stop_event.set()


sound_thread = SoundThread()


async def main():
    client = Client("Music Vibrator", ProtocolSpec.v3)
    connector = WebsocketConnector("ws://127.0.0.1:12345", logger=client.logger)

    try:
        await client.connect(connector)
    except Exception:
        traceback.print_exc()
        return

    await client.start_scanning()
    await asyncio.sleep(1)
    await client.stop_scanning()

    client.logger.info(f"Devices: {client.devices}")
    if len(client.devices) == 0:
        return

    global sound_thread
    sound_thread.start()

    for i in [
        (1.0, 0.1, ),
        (0, 0.1, ),
        (1.0, 0.1, ),
        (0, 0.1, ),
        (1.0, 0.1, ),
        (0, 1, ),
    ]:
        await client.devices[0].actuators[0].command(i[0])
        await asyncio.sleep(i[1])

    norm_list = list()
    norm_size = 1000

    global threshold
    while sound_thread.is_alive():
        volume_norm = sound_thread.volume_norm

        if len(norm_list) >= norm_size:
            norm_list = norm_list[len(norm_list) - norm_size + 1:]
        if volume_norm >= 0.1:
            norm_list.append(volume_norm)
        if len(norm_list) == 0:
            continue

        threshold = max(0.1, round(sum(norm_list) / len(norm_list) + threshold_adj, 2))
        vibrate = float(1 - 1 / (max(volume_norm - threshold, 0) * 5 + 1))

        sys.stdout.write(
            f"\r"
            f"Threshold: {threshold}({threshold_adj}) "
            f"Volume: {round(float(volume_norm), 2)} "
            # f"Vibrate: {round((volume_norm - threshold) / (max(norm_list) + 0.01 - threshold), 2)} "
            f"Vibrate: {round(vibrate, 2)} "
            # f"{round(sum(norm_list), 2)}/{len(norm_list)}={round(sum(norm_list) / len(norm_list), 2)}"
        )
        try:
            await client.devices[0].actuators[0].command(min(1.0, vibrate))
        except Exception:
            sound_thread.stop()
            break

    sound_thread.join()

    await client.disconnect()


def keyboard_handler(event):
    global threshold_adj
    if event.name in ["up", "w"]:
        threshold_adj = min(2.0, round(threshold_adj + 0.01, 2))
        # print(threshold)
    elif event.name in ["down", "s"]:
        threshold_adj = max(-2.0, round(threshold_adj - 0.01, 2))
        # print(threshold)
    elif event.name in ["space"]:
        global sound_thread
        sound_thread.stop()


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    keyboard.on_press(lambda event: keyboard_handler(event))
    asyncio.run(main(), debug=True)
