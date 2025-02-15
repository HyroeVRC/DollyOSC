
# Dolly OSC by Hyroe V0.1
# Made the 14/02/2025

import customtkinter as ctk
from tkinter import filedialog, messagebox
from pythonosc.udp_client import SimpleUDPClient
from pythonosc.dispatcher import Dispatcher
from pythonosc import osc_server
import json
import numpy as np
import copy
import os
from scipy.spatial.transform import Rotation as R
import threading

OSC_IP = "127.0.0.1"
OSC_PORT = 9000
OSC_PORT_RECEIVE = 9001
client = SimpleUDPClient(OSC_IP, OSC_PORT)

PATH_DIRECTORY = os.path.expanduser(r"~/Documents/VRChat/CameraPaths")

current_data = None
current_file = None
translation_step_slider = None
rotation_step_slider = None
original_data = None


def send_osc_command(address, value):
    try:
        client.send_message(address, value)
        print(f"Commande OSC envoyée à {address} avec la valeur {value}")
    except Exception as e:
        print(f"Erreur lors de l'envoi de la commande OSC : {e}")


def import_path(file_path):
    global current_data, original_data, current_file, file_label
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            current_data = data
            original_data = copy.deepcopy(data)
            current_file = file_path
            file_name = os.path.basename(file_path)
        update_positions()
        file_label.configure(text=f"Loaded: {file_name}")
    except Exception as e:
        messagebox.showerror("Import Error", f"Failed to import path: {e}")
        file_label.configure(text="Failed to load file!")

def open_file_dialog():
    file_path = filedialog.askopenfilename(initialdir=PATH_DIRECTORY, title="Sélectionner un fichier",
                                           filetypes=(("JSON files", "*.json"), ("All files", "*.*")))
    if file_path:
        import_path(file_path)

def play_animation():
    send_osc_command("/dolly/Play", 1)


def stop_animation():
    send_osc_command("/dolly/Play", 0)

def update_positions():
    if current_data is not None:
        for point in current_data:
            point['Position']['X'] = round(point['Position']['X'], 9)
            point['Position']['Y'] = round(point['Position']['Y'], 9)
            point['Position']['Z'] = round(point['Position']['Z'], 9)

            point['Rotation']['X'] = round(point['Rotation']['X'], 9)
            point['Rotation']['Y'] = round(point['Rotation']['Y'], 9)
            point['Rotation']['Z'] = round(point['Rotation']['Z'], 9)

            point['LookAtMeXOffset'] = round(point.get('LookAtMeXOffset', 0.0), 9)
            point['LookAtMeYOffset'] = round(point.get('LookAtMeYOffset', 0.0), 9)

        json_string = json.dumps(current_data)
        send_osc_command("/dolly/Import", json_string)
        print("Positions updated and sent (with 9 decimal precision)!")

def adjust_position(axis, adjustment):
    global translation_step_slider, current_data
    if current_data is not None and translation_step_slider:
        step_size = translation_step_slider.get()
        for point in current_data:
            point['Position'][axis] += adjustment * step_size
        update_positions()

def reset_path_to_origin():
    global current_data, original_data
    if current_data and original_data:
        for point, original in zip(current_data, original_data):
            point['Position']['X'] = original['Position']['X']
            point['Position']['Y'] = original['Position']['Y']
            point['Position']['Z'] = original['Position']['Z']
            point['Rotation']['X'] = original['Rotation']['X']
            point['Rotation']['Y'] = original['Rotation']['Y']
            point['Rotation']['Z'] = original['Rotation']['Z']
            point['LookAtMeXOffset'] = original.get('LookAtMeXOffset', 0.0)
            point['LookAtMeYOffset'] = original.get('LookAtMeYOffset', 0.0)

        update_positions()
        print("Path and rotations have been reset to their original JSON values.")

def reset_path():
    global current_data, original_data
    if current_data and original_data:
        mean_x = np.mean([p['Position']['X'] for p in original_data])
        mean_y = np.mean([p['Position']['Y'] for p in original_data])
        mean_z = np.mean([p['Position']['Z'] for p in original_data])

        for point, original in zip(current_data, original_data):
            point['Position']['X'] = original['Position']['X'] - mean_x
            point['Position']['Y'] = original['Position']['Y'] - mean_y
            point['Position']['Z'] = original['Position']['Z'] - mean_z
            point['Rotation']['X'] = original['Rotation']['X']
            point['Rotation']['Y'] = original['Rotation']['Y']
            point['Rotation']['Z'] = original['Rotation']['Z']
            point['LookAtMeXOffset'] = original.get('LookAtMeXOffset', 0.0)
            point['LookAtMeYOffset'] = original.get('LookAtMeYOffset', 0.0)

        update_positions()
        print("Path reset to center in the world with original angles maintained.")

def rotate_path(axis, angle_deg):
    global rotation_step_slider, current_data
    if current_data is not None and rotation_step_slider:
        step_angle = angle_deg * rotation_step_slider.get()
        angle_rad = np.radians(step_angle)

        mean_x = np.mean([p['Position']['X'] for p in current_data])
        mean_y = np.mean([p['Position']['Y'] for p in current_data])
        mean_z = np.mean([p['Position']['Z'] for p in current_data])

        axis_map = {'X': [1, 0, 0], 'Y': [0, 1, 0], 'Z': [0, 0, 1]}
        rotation_quat = R.from_rotvec(angle_rad * np.array(axis_map[axis]))

        for point in current_data:
            rel_pos = np.array([
                point['Position']['X'] - mean_x,
                point['Position']['Y'] - mean_y,
                point['Position']['Z'] - mean_z
            ])
            new_rel_pos = rotation_quat.apply(rel_pos)
            point['Position']['X'] = round(new_rel_pos[0] + mean_x, 9)
            point['Position']['Y'] = round(new_rel_pos[1] + mean_y, 9)
            point['Position']['Z'] = round(new_rel_pos[2] + mean_z, 9)

            initial_rotation = R.from_euler('YXZ', [
                point['Rotation']['Y'],
                point['Rotation']['X'],
                point['Rotation']['Z']
            ], degrees=True)
            new_rotation = rotation_quat * initial_rotation
            new_euler = new_rotation.as_euler('YXZ', degrees=True)

            point['Rotation']['X'] = round((new_euler[1] + 360) % 360, 9)  # Pitch
            point['Rotation']['Y'] = round((new_euler[0] + 360) % 360, 9)  # Yaw
            point['Rotation']['Z'] = round((new_euler[2] + 360) % 360, 9)  # Roll

            if point['Rotation']['X'] > 180:
                point['Rotation']['X'] -= 360
            if point['Rotation']['Y'] > 180:
                point['Rotation']['Y'] -= 360
            if point['Rotation']['Z'] > 180:
                point['Rotation']['Z'] -= 360

        update_positions()
        print(f"Path rotated around {axis}-axis by {angle_deg}° (fixed quaternion rotation)")

def osc_callback(address, *args):
    global rotation_label, translation_label
    if address == "/avatar/parameters/Rotation_Step":
        max_rotation = 15.00
        rotation_step_slider.configure(from_=0.01, to=max_rotation)
        rotation_step_slider.set(args[0] * max_rotation)
        rotation_label.configure(text=f"Value: {float(rotation_step_slider.get()):.2f}°")
    elif address == "/avatar/parameters/Translation_Step":
        max_translation = 5.00
        translation_step_slider.configure(from_=0.01, to=max_translation)
        translation_step_slider.set(args[0] * max_translation)
        translation_label.configure(text=f"Value: {float(translation_step_slider.get()):.2f} m")
    elif address == "/avatar/parameters/Play_Dolly" and args[0] == 1:
        play_animation()
    elif address == "/avatar/parameters/Stop_Dolly" and args[0] == 1:
        stop_animation()
    elif address == "/avatar/parameters/Reset_World" and args[0] == 1:
        reset_path()
    elif address == "/avatar/parameters/Reset_Origin" and args[0] == 1:
        reset_path_to_origin()
    elif address == "/avatar/parameters/X_T_Plus" and args[0] == 1:
        adjust_position('X', translation_step_slider.get())
    elif address == "/avatar/parameters/X_T_Minus" and args[0] == 1:
        adjust_position('X', -translation_step_slider.get())
    elif address == "/avatar/parameters/Y_T_Plus" and args[0] == 1:
        adjust_position('Y', translation_step_slider.get())
    elif address == "/avatar/parameters/Y_T_Minus" and args[0] == 1:
        adjust_position('Y', -translation_step_slider.get())
    elif address == "/avatar/parameters/Z_T_Plus" and args[0] == 1:
        adjust_position('Z', translation_step_slider.get())
    elif address == "/avatar/parameters/Z_T_Minus" and args[0] == 1:
        adjust_position('Z', -translation_step_slider.get())
    elif address == "/avatar/parameters/X_R_Plus" and args[0] == 1:
        rotate_path('X', rotation_step_slider.get())
    elif address == "/avatar/parameters/X_R_Minus" and args[0] == 1:
        rotate_path('X', -rotation_step_slider.get())
    elif address == "/avatar/parameters/Y_R_Plus" and args[0] == 1:
        rotate_path('Y', rotation_step_slider.get())
    elif address == "/avatar/parameters/Y_R_Minus" and args[0] == 1:
        rotate_path('Y', -rotation_step_slider.get())
    elif address == "/avatar/parameters/Z_R_Plus" and args[0] == 1:
        rotate_path('Z', rotation_step_slider.get())
    elif address == "/avatar/parameters/Z_R_Minus" and args[0] == 1:
        rotate_path('Z', -rotation_step_slider.get())

def start_osc_server():
    dispatcher = Dispatcher()
    dispatcher.map("/*", osc_callback)
    server = osc_server.ThreadingOSCUDPServer((OSC_IP, OSC_PORT_RECEIVE), dispatcher)
    server.serve_forever()

file_label = None

def setup_ui(root):
    global file_label
    root.title("Dolly Control by Hyroe V0.1")
    root.geometry("400x800")
    root.resizable(True, True)
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)

    create_main_buttons(root)
    create_sliders(root)
    configure_controls(root)
    create_quit_button(root)

    file_label = ctk.CTkLabel(root, text="", width=320, height=25)
    file_label.grid(row=5, column=0, sticky="n", padx=20, pady=(5, 10))


def create_main_buttons(root):
    btn_import = ctk.CTkButton(root, text="Import JSON Path", command=open_file_dialog)
    btn_import.grid(row=0, column=0, sticky="n", padx=20, pady=(10, 5))

    btn_play = ctk.CTkButton(root, text="Play Animation", command=play_animation,
                             fg_color="green", hover_color="light green")
    btn_play.grid(row=1, column=0, sticky="n", padx=20, pady=5)

    btn_stop = ctk.CTkButton(root, text="Stop Animation", command=stop_animation,
                             fg_color="red", hover_color="light coral")
    btn_stop.grid(row=2, column=0, sticky="n", padx=20, pady=5)

    btn_reset = ctk.CTkButton(root, text="Reset Path to World", command=reset_path,
                              fg_color="grey", hover_color="light grey")
    btn_reset.grid(row=3, column=0, sticky="n", padx=20, pady=(5, 5))

    btn_reset_origin = ctk.CTkButton(root, text="Reset Path to Origin Loaded", command=reset_path_to_origin,
                                     fg_color="grey", hover_color="light grey")
    btn_reset_origin.grid(row=4, column=0, sticky="n", padx=20, pady=(5, 10))

def create_sliders(root):
    global translation_step_slider, rotation_step_slider, translation_label, rotation_label

    slider_frame = ctk.CTkFrame(root)
    slider_frame.grid(row=6, column=0, sticky="n", padx=10, pady=10)
    root.grid_rowconfigure(4, weight=2)
    root.grid_columnconfigure(0, weight=1)

    def update_translation_label(value):
        translation_label.configure(text=f"Value: {float(value):.2f} m")

    def update_rotation_label(value):
        rotation_label.configure(text=f"Value: {float(value):.2f}°")

    Stept = ctk.CTkLabel(slider_frame, text="Step Translation")
    Stept.grid(row=0, column=0, sticky="n", pady=(10, 5))
    translation_step_slider = ctk.CTkSlider(slider_frame, from_=0.01, to=15.00, number_of_steps=200, command=update_translation_label)
    translation_step_slider.grid(row=1, column=0, sticky="n")
    translation_step_slider.set(0.5)
    translation_label = ctk.CTkLabel(slider_frame, text=f"Value: {translation_step_slider.get():.2f} m")
    translation_label.grid(row=1, column=1, padx=(10, 0))

    Stepr = ctk.CTkLabel(slider_frame, text="Step Rotation")
    Stepr.grid(row=2, column=0, sticky="n", pady=(10, 5))
    rotation_step_slider = ctk.CTkSlider(slider_frame, from_=0.01, to=15.00, number_of_steps=200, command=update_rotation_label)
    rotation_step_slider.grid(row=3, column=0, sticky="n")
    rotation_step_slider.set(1.0)
    rotation_label = ctk.CTkLabel(slider_frame, text=f"Value: {rotation_step_slider.get():.2f}°")
    rotation_label.grid(row=3, column=1, padx=(10, 0))

def create_axis_buttons(frame, axis, row):
    frame.grid_columnconfigure(0, weight=1)
    frame.grid_columnconfigure(1, weight=1)

    increase_btn = ctk.CTkButton(frame, text=f"+ {axis}", command=lambda: adjust_position(axis, 1))
    increase_btn.grid(row=row, column=0, padx=5, pady=5, sticky="nsew")

    decrease_btn = ctk.CTkButton(frame, text=f"- {axis}", command=lambda: adjust_position(axis, -1))
    decrease_btn.grid(row=row, column=1, padx=5, pady=5, sticky="nsew")

    rotate_pos_btn = ctk.CTkButton(frame, text=f"Rotate +{axis}", command=lambda: rotate_path(axis, 5))
    rotate_pos_btn.grid(row=row+1, column=0, padx=5, pady=5, sticky="nsew")

    rotate_neg_btn = ctk.CTkButton(frame, text=f"Rotate -{axis}", command=lambda: rotate_path(axis, -5))
    rotate_neg_btn.grid(row=row+1, column=1, padx=5, pady=5, sticky="nsew")

    for i in range(2):
        frame.grid_columnconfigure(i, weight=1)


def configure_controls(root):
    frame_controls = ctk.CTkFrame(root)
    frame_controls.grid(row=7, column=0, sticky="n", padx=20, pady=10)
    root.grid_rowconfigure(6, weight=1)
    root.grid_columnconfigure(0, weight=1)
    for i, axis in enumerate(['X', 'Y', 'Z']):
        create_axis_controls(frame_controls, axis, i)


def create_axis_controls(frame, axis, row):
    axis_frame = ctk.CTkFrame(frame)
    axis_frame.grid(row=row, column=0, sticky="nsew")

    label = ctk.CTkLabel(axis_frame, text=f"Axis {axis} Controls:")
    label.grid(row=0, column=0, columnspan=2, sticky="n")

    create_axis_buttons(axis_frame, axis, 1)
    axis_frame.grid_columnconfigure(0, weight=1)
    axis_frame.grid_columnconfigure(1, weight=1)


def create_quit_button(root):
    btn_quit = ctk.CTkButton(root, text="Quit", command=root.quit)
    btn_quit.grid(row=8, column=0, sticky="n", padx=20, pady=(10, 20))

if __name__ == "__main__":
    osc_thread = threading.Thread(target=start_osc_server, daemon=True)
    osc_thread.start()
    root = ctk.CTk()
    setup_ui(root)
    root.mainloop()
