from fbs_runtime.application_context.PyQt5 import ApplicationContext
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QTabWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, QToolButton, QHBoxLayout, QSizePolicy

import sys
import json
import struct
import lzma

from flowlayout import FlowLayout
from util import tr, find_vial_keyboards, open_device, hid_send, MSG_LEN
from kle_serial import Serial as KleSerial

class TabbedKeycodes(QTabWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab_basic = QWidget()
        layout = FlowLayout()

        for lbl in ["", "hello", "Esc", "A", "B", "C", "D", "E", "F"]:
            btn = QPushButton(lbl)
            btn.setFixedSize(50, 50)
            layout.addWidget(btn)
        self.tab_basic.setLayout(layout)

        self.tab_media = QWidget()
        self.tab_macro = QWidget()

        self.addTab(self.tab_basic, tr("TabbedKeycodes", "Basic"))
        self.addTab(self.tab_media, tr("TabbedKeycodes", "Media"))
        self.addTab(self.tab_macro, tr("TabbedKeycodes", "Macro"))


KEY_WIDTH = 40
KEY_HEIGHT = KEY_WIDTH
KEY_SPACING = 4


class KeyboardContainer(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.layout_layers = QHBoxLayout()
        layer_label = QLabel(tr("KeyboardContainer", "Layer"))

        layout_labels_container = QHBoxLayout()
        layout_labels_container.addWidget(layer_label)
        layout_labels_container.addLayout(self.layout_layers)
        layout_labels_container.addStretch()

        # contains the actual keyboard
        self.container = QWidget()

        layout = QVBoxLayout()
        layout.addLayout(layout_labels_container)
        layout.addWidget(self.container)
        layout.setAlignment(self.container, Qt.AlignHCenter)
        self.setLayout(layout)

        self.keys = []
        self.layer_labels = []

    def rebuild_layers(self):
        for label in self.layer_labels:
            label.deleteLater()
        self.layer_labels = []

        # create new layer labels
        for x in range(self.layers):
            label = QLabel(str(x))
            label.setStyleSheet("border: 1px solid black; padding: 5px")
            label.setAlignment(Qt.AlignCenter)
            self.layout_layers.addWidget(label)
            self.layer_labels.append(label)

    def rebuild(self, dev, data):
        # delete current layout
        for key in self.keys:
            key.deleteLater()
        self.keys = []

        # get number of layers
        self.layers = hid_send(dev, b"\x11")[1]
        self.rebuild_layers()

        serial = KleSerial()
        kb = serial.deserialize(data["layouts"]["keymap"])

        max_w = max_h = 0

        for key in kb.keys:
            widget = QLabel()

            if key.labels[0] and "," in key.labels[0]:
                row, col = key.labels[0].split(",")
                row, col = int(row), int(col)
                data = hid_send(dev, b"\x04" + struct.pack("<BBB", 0, row, col))
                keycode = struct.unpack(">H", data[4:6])[0]
                widget.setText("0x{:X}".format(keycode))

            widget.setParent(self.container)
            widget.setStyleSheet('background-color:white; border: 1px solid black')
            widget.setAlignment(Qt.AlignCenter)

            x = (KEY_WIDTH + KEY_SPACING) * key.x
            y = (KEY_HEIGHT + KEY_SPACING) * key.y
            w = (KEY_WIDTH + KEY_SPACING) * key.width - KEY_SPACING
            h = (KEY_HEIGHT + KEY_SPACING) * key.height - KEY_SPACING

            widget.setFixedSize(w, h)
            widget.move(x, y)
            widget.show()

            # print("{} {}x{}+{}x{}".format(key.labels, key.x, key.y, key.width, key.height))

            max_w = max(max_w, x + w)
            max_h = max(max_h, y + h)

            self.keys.append(widget)

        self.container.setFixedSize(max_w, max_h)


class MainWindow(QWidget):

    def __init__(self):
        super().__init__()
        self.device = None
        self.devices = []

        self.keyboard_container = KeyboardContainer()

        self.tabbed_keycodes = TabbedKeycodes()

        self.combobox_devices = QComboBox()
        self.combobox_devices.currentIndexChanged.connect(self.on_device_selected)

        btn_refresh_devices = QToolButton()
        btn_refresh_devices.setToolButtonStyle(Qt.ToolButtonTextOnly)
        btn_refresh_devices.setText(tr("MainWindow", "Refresh"))
        btn_refresh_devices.clicked.connect(self.on_click_refresh)

        layout_combobox = QHBoxLayout()
        layout_combobox.addWidget(self.combobox_devices)
        layout_combobox.addWidget(btn_refresh_devices)

        layout = QVBoxLayout()
        layout.addLayout(layout_combobox)
        layout.addWidget(self.keyboard_container)
        layout.addWidget(self.tabbed_keycodes)
        self.setLayout(layout)

        # make sure initial state is valid
        self.on_click_refresh()
        self.on_device_selected()

    def on_click_refresh(self):
        self.devices = find_vial_keyboards()
        self.combobox_devices.clear()

        for dev in self.devices:
            self.combobox_devices.addItem("{} {}".format(dev["manufacturer_string"], dev["product_string"]))

    def on_device_selected(self):
        self.device = None
        idx = self.combobox_devices.currentIndex()
        if idx >= 0:
            self.device = open_device(self.devices[idx])
            self.reload_layout()

    def reload_layout(self):
        """ Requests layout data from the current device """

        # get the size
        data = hid_send(self.device, b"\xFE\x01")
        sz = struct.unpack("<I", data[0:4])[0]

        # get the payload
        payload = b""
        block = 0
        while sz > 0:
            data = hid_send(self.device, b"\xFE\x02" + struct.pack("<I", block))
            if sz < MSG_LEN:
                data = data[:sz]
            payload += data
            block += 1
            sz -= MSG_LEN

        payload = json.loads(lzma.decompress(payload))
        self.keyboard_container.rebuild(self.device, payload)


if __name__ == '__main__':
    appctxt = ApplicationContext()       # 1. Instantiate ApplicationContext
    window = MainWindow()
    window.resize(1024, 768)
    window.show()
    exit_code = appctxt.app.exec_()      # 2. Invoke appctxt.app.exec_()
    sys.exit(exit_code)