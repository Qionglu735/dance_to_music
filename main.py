
import aubio
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

threshold_adj = 0.32
sample_size = 100
sample_size_adj = 32


class SoundThread(threading.Thread):
    def __init__(self):
        super(SoundThread, self).__init__()
        self._stop_event = threading.Event()
        self.volume_norm = 0
        # self.pitch_o = aubio.pitch("default", buf_size=512, hop_size=512, samplerate=44100)
        # self.pitch_o.set_unit("midi")
        # self.pitch_o.set_tolerance(0.8)
        # self.pitch = 0

    def print_sound(self, indata, outdata, frames, time, status):
        self.volume_norm = np.linalg.norm(indata)
        # self.pitch = self.pitch_o(indata[:, 0])[0]
        # print(f"{self.volume_norm}")

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
            # print(_in, _out)
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

    volume_list = list()
    pitch_list = list()
    while sound_thread.is_alive():
        try:
            client = Client("Music Vibrator", ProtocolSpec.v3)
            connector = WebsocketConnector("ws://127.0.0.1:22345", logger=client.logger)
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
            volume = sound_thread.volume_norm * 100
            # pitch = sound_thread.pitch

            if volume >= 0.0001:
                volume_list.append(volume)
            if len(volume_list) > sample_size * sample_size_adj:
                volume_list = volume_list[len(volume_list) - sample_size * sample_size_adj:]
            if len(volume_list) == 0:
                print("len(volume_list) == 0 continue")
                continue

            # if volume >= 0.01:
            #     pitch_list.append(pitch)
            # if len(pitch_list) > sample_size * sample_size_adj:
            #     pitch_list = pitch_list[len(pitch_list) - sample_size * sample_size_adj:]

            # volume_threshold = max(0.01, round(sum(volume_list) / len(volume_list) * 2 * threshold_adj, 2))
            # average of volume
            volume_avg = sum(volume_list) / len(volume_list)
            volume_avg = max(0.0001, round(volume_avg, 4))
            # average of volume * adj
            volume_avg_adj = sum(volume_list) / len(volume_list) * (1 + threshold_adj)
            volume_avg_adj = max(0.0001, round(volume_avg_adj, 4))
            # # distance between min and max value * adj
            # volume_dis_adj = min(volume_list) + (max(volume_list) - min(volume_list)) * (0.5 + threshold_adj)
            # volume_dis_adj = max(0.01, round(volume_dis_adj, 2))

            volume_vibrate = float(1 - 1 / (max(volume - volume_avg_adj, 0) + 1))

            # # average of pitch
            # pitch_avg = sum(pitch_list) / len(pitch_list)
            # pitch_avg = max(0.01, round(pitch_avg, 2))
            # # average of pitch * adj
            # pitch_avg_adj = sum(pitch_list) / len(pitch_list) * (1 + threshold_adj)
            # pitch_avg_adj = max(0.01, round(pitch_avg_adj, 2))
            # # distance between min and max value * adj
            # pitch_dis_adj = min(pitch_list) + (max(pitch_list) - min(pitch_list)) * (0.5 + threshold_adj)
            # pitch_dis_adj = max(0.01, round(pitch_dis_adj, 2))
            #
            # pitch_vibrate = float(1 - 1 / (max(pitch - pitch_avg_adj, 0) + 1))

            vibrate = max([
                volume_vibrate,
                # pitch_vibrate,
            ])

            def bar_displayer(value, avg, avg_adj, value_list):
                bar_size = 70
                bar_low_end = 0
                bar_base = max(1, max(value_list) - bar_low_end)
                bar = int(math.floor((value - bar_low_end) / bar_base * bar_size))
                avg_bar = int(math.floor((avg - bar_low_end) / bar_base * bar_size))
                avg_adj_bar = int(math.floor((avg_adj - bar_low_end) / bar_base * bar_size))
                bar_display = list(f"{'=' * bar }{' ' * (bar_size - bar)}")
                if avg_bar < len(bar_display):
                    bar_display[avg_bar] = "$"  # avg
                if avg_adj_bar < len(bar_display):
                    if bar_display[avg_adj_bar] == "=":
                        bar_display[avg_adj_bar] = "!"  # avg * adj (active)
                    else:
                        bar_display[avg_adj_bar] = "|"  # avg * adj
                return "".join(bar_display)

            display = bar_displayer(volume, volume_avg, volume_avg_adj, volume_list)
            # display = bar_displayer(pitch, pitch_avg, pitch_avg_adj, pitch_list)

            sys.stdout.write(
                f"\r"
                f"[{display}] "
                f"Volume: {round(float(volume), 4)}/{volume_avg} ({threshold_adj}) "
                # f"Pitch: {round(float(pitch), 2)}/{pitch_avg}/{pitch_dis_adj} ({threshold_adj}) "
                f"Vibrate: {round(vibrate, 2)} "
                f"Sample: {len(volume_list)}/{sample_size * sample_size_adj} "
                # f"Sample: {len(pitch_list)}/{sample_size * sample_size_adj} "
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
    global sample_size_adj
    if event.name in ["up", "w"]:
        threshold_adj = min(2.0, round(threshold_adj + 0.01, 2))
        # print(threshold)
    elif event.name in ["down", "s"]:
        threshold_adj = max(-2.0, round(threshold_adj - 0.01, 2))
        # print(threshold)
    elif event.name in ["left", "a"]:
        sample_size_adj = max(1, math.floor(sample_size_adj / 2))
        # print(threshold)
    elif event.name in ["right", "d"]:
        sample_size_adj = sample_size_adj * 2
        # print(threshold)
    elif event.name in ["esc", "space"]:
        global sound_thread
        sound_thread.stop()


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    keyboard.on_press(lambda event: keyboard_handler(event))
    asyncio.run(main(), debug=True)
