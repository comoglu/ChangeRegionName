#!/opt/neac-python/.venv/bin/python

# Add these two lines at the top to suppress PyQt5 deprecation warnings
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="PyQt5")

import json
import math
import os
import sys
from dataclasses import dataclass
from typing import Dict, List

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QShortcut,
    QSpinBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QRadioButton,
    QButtonGroup,
)

import seiscomp.datamodel as DM
from seiscomp.client import Application
from seiscomp.core import Time

DESC_TYPE = DM.REGION_NAME


@dataclass
class Location:
    id: int = None
    type: str = None
    name: str = None
    lat: float = None
    lon: float = None
    population: int = None
    admin_level: str = None
    state: str = None
    country: str = None
    postcode: str = None
    state_full: str = None

    @classmethod
    def from_dict(cls, data: Dict):
        cleaned_data = {k: (None if v == "" else v) for k, v in data.items()}
        return cls(**cleaned_data)


class StyleSheet:
    MAIN = """
        QMainWindow {
            background-color: #f0f0f0;
        }
        QLabel {
            font-size: 12px;
            font-weight: bold;
            color: #2c3e50;
        }
        QLineEdit {
            padding: 8px;
            border: 2px solid #bdc3c7;
            border-radius: 4px;
            background-color: white;
            font-size: 12px;
        }
        QLineEdit:read-only {
            background-color: #ecf0f1;
        }
        QPushButton {
            padding: 8px 15px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 12px;
            min-width: 100px;
        }
        QPushButton:enabled {
            background-color: #3498db;
            color: white;
            border: none;
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
        QPushButton:disabled {
            background-color: #bdc3c7;
            color: #7f8c8d;
        }
        QTableWidget {
            background-color: white;
            alternate-background-color: #f9f9f9;
        }
        QGroupBox {
            border: 2px solid #bdc3c7;
            border-radius: 4px;
            margin-top: 1ex;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
        }
        QRadioButton {
            margin: 2px;
        }
    """


class LocationFinder:
    # Define direction options with different levels of detail
    DIRECTIONS_4 = ["N", "E", "S", "W"]
    DIRECTIONS_8 = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    DIRECTIONS_16 = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
    ]
    
    @staticmethod
    def load_locations(filename: str) -> List[Location]:
        with open(filename, "r") as f:
            data = json.load(f)
            return [Location.from_dict(loc) for loc in data]

    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371  # Earth's radius in kilometers

        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c

        return distance

    @staticmethod
    def get_cardinal_direction(
        lat1: float, lon1: float, lat2: float, lon2: float, direction_type="16"
    ) -> str:
        dLat = lat2 - lat1
        dLon = lon2 - lon1

        angle = math.degrees(math.atan2(dLon, dLat))
        angle = (angle + 360) % 360
        
        # Select the appropriate directions list based on direction_type
        if direction_type == "4":
            directions = LocationFinder.DIRECTIONS_4
            idx = int((angle + 45) / 90) % 4
        elif direction_type == "8":
            directions = LocationFinder.DIRECTIONS_8
            idx = int((angle + 22.5) / 45) % 8
        else:  # Default to 16 directions
            directions = LocationFinder.DIRECTIONS_16
            idx = int((angle + 11.25) / 22.5) % 16
            
        return directions[idx]


class LocationTab(QWidget):
    region_name_updated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.locations = []
        self.all_nearby_locations = []  
        self.direction_type = "16"  # Default to 16 directions
        self.setup_ui()
        self.load_locations()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Input group
        input_group = QGroupBox("Search Parameters")
        input_layout = QFormLayout()

        self.lat_input = QDoubleSpinBox()
        self.lat_input.setRange(-90, 90)
        self.lat_input.setDecimals(6)

        self.lon_input = QDoubleSpinBox()
        self.lon_input.setRange(-180, 180)
        self.lon_input.setDecimals(6)

        self.distance_input = QSpinBox()
        self.distance_input.setRange(1, 1000)
        self.distance_input.setValue(100)

        self.count_input = QSpinBox()
        self.count_input.setRange(1, 50)
        self.count_input.setValue(10)

        input_layout.addRow("Latitude:", self.lat_input)
        input_layout.addRow("Longitude:", self.lon_input)
        input_layout.addRow("Max Distance (km):", self.distance_input)
        input_layout.addRow("Max Locations:", self.count_input)

        # Add direction precision options
        direction_layout = QHBoxLayout()
        direction_label = QLabel("Direction Precision:")
        self.direction_group = QButtonGroup(self)
        
        self.radio_4_dirs = QRadioButton("4 Directions (N,E,S,W)")
        self.radio_8_dirs = QRadioButton("8 Directions (N,NE,E...)")
        self.radio_16_dirs = QRadioButton("16 Directions (N,NNE,NE...)")
        self.radio_16_dirs.setChecked(True)  # Default
        
        self.direction_group.addButton(self.radio_4_dirs, 1)
        self.direction_group.addButton(self.radio_8_dirs, 2)
        self.direction_group.addButton(self.radio_16_dirs, 3)
        
        self.direction_group.buttonClicked.connect(self.change_direction_type)
        
        direction_layout.addWidget(direction_label)
        direction_layout.addWidget(self.radio_4_dirs)
        direction_layout.addWidget(self.radio_8_dirs)
        direction_layout.addWidget(self.radio_16_dirs)
        
        direction_group_widget = QWidget()
        direction_group_widget.setLayout(direction_layout)
        input_layout.addRow("", direction_group_widget)

        # Add hamlet visibility toggle
        self.show_hamlets = QCheckBox("Show hamlets")
        self.show_hamlets.setChecked(False)  # Default no showing hamlets
        self.show_hamlets.stateChanged.connect(self.filter_results)
        input_layout.addRow("", self.show_hamlets)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # Search button
        self.search_button = QPushButton("Find Nearby Locations")
        self.search_button.clicked.connect(self.find_locations)
        layout.addWidget(self.search_button)

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels(
            ["Name", "Type", "State", "Distance (km)", "Direction", "Population"]
        )
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SingleSelection)
        self.results_table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.results_table)

        # Add region name preview group
        preview_group = QGroupBox("Region Name Preview")
        preview_layout = QVBoxLayout()

        self.region_preview = QLineEdit()
        self.region_preview.setReadOnly(True)
        self.region_preview.setPlaceholderText(
            "Select a location to preview region name..."
        )
        preview_layout.addWidget(self.region_preview)

        # Add format selection
        format_layout = QHBoxLayout()
        self.format_label = QLabel("Format:")
        self.format_combo = QComboBox()
        self.format_combo.addItems(
            [
                "DIRECTION of NAME, STATE",
                "NAME, DIRECTION at DISTANCE km",
                "DISTANCE km DIRECTION of NAME",
                "NAME (DIRECTION, DISTANCE km)",
                "DISTANCE km DIRECTION of NAME, STATE",
            ]
        )
        self.format_combo.currentIndexChanged.connect(self.update_preview)
        format_layout.addWidget(self.format_label)
        format_layout.addWidget(self.format_combo)
        preview_layout.addLayout(format_layout)

        # Add use region button
        self.use_region_btn = QPushButton("Use This Region Name")
        self.use_region_btn.setEnabled(False)
        self.use_region_btn.clicked.connect(self.use_region_name)
        preview_layout.addWidget(self.use_region_btn)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

    def change_direction_type(self, button):
        """Change the direction type based on the selected radio button"""
        if button == self.radio_4_dirs:
            self.direction_type = "4"
        elif button == self.radio_8_dirs:
            self.direction_type = "8"
        else:  # 16 directions
            self.direction_type = "16"
            
        # If we have locations, update the display
        if self.all_nearby_locations:
            self.refresh_directions()
    
    def refresh_directions(self):
        """Refresh directions in the table with the current direction type"""
        # Get current coordinates
        lat = self.lat_input.value()
        lon = self.lon_input.value()
        
        # Update directions for all locations
        for i, (loc, distance, _) in enumerate(self.all_nearby_locations):
            # Calculate new direction with current precision setting
            direction = LocationFinder.get_cardinal_direction(
                loc.lat, loc.lon, lat, lon, self.direction_type
            )
            # Update the stored direction
            self.all_nearby_locations[i] = (loc, distance, direction)
        
        # Update displayed results
        self.filter_results()
        
        # Update preview if a row is selected
        self.update_preview()

    def update_region_name(self, new_name):
        self.region_input.setText(new_name)
        self.edit_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.tab_widget.setCurrentIndex(0)  # Switch back to region editor tab
        self.show_status("Region name updated from location selection")

    def load_locations(self):
        try:
            share_folder = os.getenv("EATWS_SHARE_FOLDER")
            if not share_folder:
                raise ValueError("EATWS_SHARE_FOLDER environment variable is not set")

            locations_path = os.path.join(share_folder, "locations.json")
            self.locations = LocationFinder.load_locations(locations_path)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load locations: {str(e)}")

    def find_locations(self):
        lat = self.lat_input.value()
        lon = self.lon_input.value()
        max_distance = self.distance_input.value()
        max_count = self.count_input.value()
        show_hamlets = self.show_hamlets.isChecked()

        # Calculate distances and directions
        nearby_locations = []
        for loc in self.locations:
            distance = LocationFinder.calculate_distance(lat, lon, loc.lat, loc.lon)
            if distance <= max_distance:
                # Swap coordinates to get direction FROM location TO event using the selected direction type
                direction = LocationFinder.get_cardinal_direction(
                    loc.lat, loc.lon, lat, lon, self.direction_type
                )
                nearby_locations.append((loc, distance, direction))

        # Sort by distance and limit to max_count
        nearby_locations.sort(key=lambda x: x[1])
        nearby_locations = nearby_locations[:max_count]
        
        # Store all locations for hamlet filtering
        self.all_nearby_locations = nearby_locations
        
        # Filter hamlet locations if needed
        filtered_locations = nearby_locations
        if not show_hamlets:
            filtered_locations = [
                loc for loc in nearby_locations
                if not (loc[0].type and loc[0].type.lower() == "hamlet")
            ]

        # Update table
        self.update_results_table(filtered_locations)

    def on_selection_changed(self):
        selected_items = self.results_table.selectedItems()
        if selected_items:
            self.update_preview()
            self.use_region_btn.setEnabled(True)
        else:
            self.region_preview.clear()
            self.use_region_btn.setEnabled(False)

    def update_preview(self):
        selected_row = self.results_table.currentRow()
        if selected_row >= 0:
            name = self.results_table.item(selected_row, 0).text()
            state = self.results_table.item(selected_row, 2).text()
            distance = self.results_table.item(selected_row, 3).text()
            direction = self.results_table.item(selected_row, 4).text()

            format_idx = self.format_combo.currentIndex()
            if format_idx == 0:
                preview = f"{direction} of {name}, {state}"
            elif format_idx == 1:
                preview = f"{name}, {direction} at {distance} km"
            elif format_idx == 2:
                preview = f"{distance} km {direction} of {name}"
            elif format_idx == 3:
                preview = f"{name} ({direction}, {distance} km)"
            else:
                preview = f"{distance} km {direction} of {name}, {state}"

            self.region_preview.setText(preview)

    def use_region_name(self):
        if self.region_preview.text():
            self.region_name_updated.emit(self.region_preview.text())

    def filter_results(self):
        """Filter results based on current hamlet visibility setting"""
        if not self.all_nearby_locations:
            return  # No locations to filter yet

        show_hamlets = self.show_hamlets.isChecked()
        filtered_locations = self.all_nearby_locations

        if not show_hamlets:
            filtered_locations = [
                loc
                for loc in self.all_nearby_locations
                if not (loc[0].type and loc[0].type.lower() == "hamlet")
            ]

        self.update_results_table(filtered_locations)

    def update_results_table(self, locations):
        """Update the table with the given locations"""
        self.results_table.setRowCount(len(locations))
        for i, (loc, distance, direction) in enumerate(locations):
            self.results_table.setItem(i, 0, QTableWidgetItem(str(loc.name or "N/A")))
            self.results_table.setItem(i, 1, QTableWidgetItem(str(loc.type or "N/A")))
            self.results_table.setItem(i, 2, QTableWidgetItem(str(loc.state or "N/A")))
            self.results_table.setItem(i, 3, QTableWidgetItem(f"{distance:.1f}"))
            self.results_table.setItem(i, 4, QTableWidgetItem(direction))
            self.results_table.setItem(
                i,
                5,
                QTableWidgetItem(
                    str(loc.population if loc.population is not None else "N/A")
                ),
            )

        self.results_table.resizeColumnsToContents()


class RegionChangerWindow(QMainWindow):
    def __init__(self, app_instance, parent=None):
        super().__init__(parent)
        self.app_instance = app_instance
        self.setup_ui()

        # Store current event and description
        self.current_event = None
        self.current_desc = None
        self.op = None

    def setup_ui(self):
        self.setWindowTitle("SeisComP Region Manager")
        self.setStyleSheet(StyleSheet.MAIN)

        # Create central widget with tab widget
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # Create and add tabs
        self.region_tab = self.create_region_tab()
        self.location_tab = LocationTab()

        # Connect location tab signals
        self.location_tab.region_name_updated.connect(self.update_region_name)

        self.tab_widget.addTab(self.region_tab, "Region Editor")
        self.tab_widget.addTab(self.location_tab, "Location Finder")

        # Add status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Enter an Event ID to begin")

        # Set window size
        self.setMinimumSize(800, 600)

    def update_region_name(self, new_name):
        self.region_input.setText(new_name)
        self.edit_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.tab_widget.setCurrentIndex(0)  # Switch back to region editor tab
        self.show_status("Region name updated from location selection")

    def create_region_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Event ID group
        event_group = QGroupBox("Event Information")
        event_layout = QFormLayout()

        self.event_id_input = QLineEdit()
        self.event_id_input.setPlaceholderText("Enter event ID here...")
        self.event_id_input.returnPressed.connect(self.fetch_region)

        self.region_input = QLineEdit()
        self.region_input.setPlaceholderText("Fetch an event to see its region...")
        self.region_input.setReadOnly(True)

        # Add coordinate display fields
        self.lat_display = QLineEdit()
        self.lat_display.setReadOnly(True)
        self.lat_display.setPlaceholderText("Latitude will appear here...")

        self.lon_display = QLineEdit()
        self.lon_display.setReadOnly(True)
        self.lon_display.setPlaceholderText("Longitude will appear here...")

        event_layout.addRow("Event ID (Press Enter to fetch):", self.event_id_input)
        event_layout.addRow("Region Name:", self.region_input)
        event_layout.addRow("Latitude:", self.lat_display)
        event_layout.addRow("Longitude:", self.lon_display)

        # Add a button to show nearby locations
        self.show_locations_btn = QPushButton("Show Nearby Locations")
        self.show_locations_btn.setEnabled(False)
        self.show_locations_btn.clicked.connect(self.show_nearby_locations)
        event_layout.addRow("", self.show_locations_btn)

        event_group.setLayout(event_layout)
        layout.addWidget(event_group)

        # Custom region input
        custom_group = QGroupBox("Custom Region Input")
        custom_layout = QFormLayout()
        
        self.custom_region_input = QLineEdit()
        self.custom_region_input.setPlaceholderText("Enter a custom region name...")
        
        self.use_custom_btn = QPushButton("Use Custom Region")
        self.use_custom_btn.clicked.connect(self.use_custom_region)
        
        custom_layout.addRow("Custom Region:", self.custom_region_input)
        custom_layout.addRow("", self.use_custom_btn)
        
        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)

        # Button group
        button_layout = QHBoxLayout()

        self.fetch_button = QPushButton("Fetch Region (F5)")
        self.edit_button = QPushButton("Edit Region (F2)")
        self.save_button = QPushButton("Save Changes (Ctrl+S)")

        self.edit_button.setEnabled(False)
        self.save_button.setEnabled(False)

        self.fetch_button.clicked.connect(self.fetch_region)
        self.edit_button.clicked.connect(self.enable_edit)
        self.save_button.clicked.connect(self.save_changes)

        button_layout.addWidget(self.fetch_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.save_button)

        layout.addLayout(button_layout)
        layout.addStretch()

        # Setup keyboard shortcuts
        QShortcut(QKeySequence("F5"), self).activated.connect(self.fetch_region)
        QShortcut(QKeySequence("F2"), self).activated.connect(self.enable_edit)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_changes)
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.close)

        return widget
    
    def use_custom_region(self):
        """Use the custom region text entered by the user"""
        custom_text = self.custom_region_input.text().strip()
        if custom_text:
            self.region_input.setText(custom_text)
            self.edit_button.setEnabled(True)
            self.save_button.setEnabled(True)
            self.show_status("Custom region name applied")
        else:
            QMessageBox.warning(self, "Error", "Please enter a custom region name first")

    def show_status(self, message, timeout=0):
        self.status_bar.showMessage(message, timeout)

    def fetch_region(self):
        event_id = self.event_id_input.text().strip()
        if not event_id:
            QMessageBox.warning(self, "Error", "Please enter an Event ID")
            return

        self.show_status("Fetching region information...")

        DM.Notifier.Enable()
        event = self.app_instance.query().getEventByPublicID(event_id)
        if not event:
            self.show_status("Error: Event not found", 3000)
            QMessageBox.warning(
                self, "Error", f"Could not find event with id {event_id}"
            )
            return

        self.app_instance.query().loadEventDescriptions(event)

        # Store current event
        self.current_event = event

        # Find current region
        current_region = ""
        for i in range(event.eventDescriptionCount()):
            desc = event.eventDescription(i)
            if desc.type() == DESC_TYPE:
                current_region = desc.text()
                self.current_desc = desc
                self.op = DM.OP_UPDATE
                break
        else:
            self.current_desc = DM.EventDescription()
            self.current_desc.setType(DESC_TYPE)
            self.current_event.add(self.current_desc)
            self.op = DM.OP_ADD

        self.region_input.setText(current_region)
        self.region_input.setReadOnly(True)

        self.edit_button.setEnabled(True)
        self.save_button.setEnabled(False)

        # Get event latitude and longitude with debug info
        try:
            preferred_origin_id = event.preferredOriginID()
            self.show_status(f"Preferred Origin ID: {preferred_origin_id}")
            print(f"Debug - Preferred Origin ID: {preferred_origin_id}")

            if not preferred_origin_id:
                raise ValueError("No preferred origin ID found")

            # Load the origin object using loadObject instead of getObject
            origin = DM.Origin.Cast(
                self.query().loadObject(DM.Origin.TypeInfo(), preferred_origin_id)
            )
            print(f"Debug - Origin object: {origin}")

            if not origin:
                raise ValueError(
                    f"Could not get origin object for ID: {preferred_origin_id}"
                )

            # Debug origin details
            print(f"Debug - Origin time: {origin.time().value()}")
            print(f"Debug - Has latitude: {origin.latitude() is not None}")
            print(f"Debug - Has longitude: {origin.longitude() is not None}")

            lat = origin.latitude().value()
            lon = origin.longitude().value()

            print(f"Debug - Latitude: {lat}")
            print(f"Debug - Longitude: {lon}")

            # Update displays in the region tab
            self.lat_display.setText(f"{lat:.6f}")
            self.lon_display.setText(f"{lon:.6f}")
            self.show_locations_btn.setEnabled(True)

            # Update location tab
            self.location_tab.lat_input.setValue(lat)
            self.location_tab.lon_input.setValue(lon)

            self.show_status(f"Successfully loaded coordinates: {lat:.6f}, {lon:.6f}")

        except Exception as e:
            error_msg = f"Could not fetch coordinates: {str(e)}"
            self.show_status(error_msg, 3000)
            print(f"Debug - Error: {error_msg}")
            print("Debug - Event details:")
            print(f"Debug - Event ID: {event.publicID()}")
            try:
                print(f"Debug - Creation time: {event.creationInfo().creationTime()}")
            except (AttributeError, TypeError) as e:
                print(f"Debug - No creation time available: {e}")
            try:
                print(f"Debug - Event type: {event.type()}")
            except (AttributeError, TypeError) as e:
                print(f"Debug - No event type available: {e}")
            self.lat_display.setText("N/A")
            self.lon_display.setText("N/A")
            self.show_locations_btn.setEnabled(False)

        self.show_status(f"Successfully fetched region for event {event_id}")

    def show_nearby_locations(self):
        self.tab_widget.setCurrentWidget(self.location_tab)
        self.location_tab.find_locations()

    def enable_edit(self):
        if self.current_event:
            self.region_input.setReadOnly(False)
            self.region_input.setFocus()
            self.save_button.setEnabled(True)
            self.show_status("Editing region - Press Ctrl+S to save changes")
        else:
            QMessageBox.warning(self, "Error", "Please fetch an event first")

    def save_changes(self):
        if not self.current_event or not self.current_desc:
            QMessageBox.warning(self, "Error", "Please fetch an event first")
            return

        new_region = self.region_input.text()
        self.current_desc.setText(new_region)
        
        # Make sure creation info exists
        if not self.current_event.creationInfo():
            self.current_event.setCreationInfo(DM.CreationInfo())
        
        self.current_event.creationInfo().setModificationTime(Time.GMT())

        self.show_status("Saving changes...")

        DM.Notifier.Create("EventParameters", DM.OP_UPDATE, self.current_event)
        DM.Notifier.Create(self.current_event, self.op, self.current_desc)
        DM.Notifier.SetEnabled(False)
        msg = DM.Notifier.GetMessage()

        try:
            self.app_instance.connection().send(msg)
            self.show_status("Region updated successfully", 3000)
            QMessageBox.information(self, "Success", "Region updated successfully")
            self.region_input.setReadOnly(True)
            self.save_button.setEnabled(False)
        except Exception as e:
            self.show_status("Error: Failed to update region", 3000)
            QMessageBox.critical(self, "Error", f"Failed to update region: {str(e)}")

    def query(self):
        return self.app_instance.query()


class RegionChanger(Application):
    def __init__(self, *args):
        Application.__init__(self, len(args), list(args))

        self.setMessagingEnabled(True)
        self.setDatabaseEnabled(True, True)
        self.setDaemonEnabled(False)
        self.setPrimaryMessagingGroup("EVENT")

        # Initialize Qt Application
        self.app = QApplication(sys.argv)
        self.window = None

    def init(self):
        if not Application.init(self):
            return False
        return True

    def run(self):
        try:
            self.window = RegionChangerWindow(self)
            self.window.show()
            exec_result = self.app.exec_()
            # Return True for successful execution (0), False for error (non-zero)
            return True if exec_result == 0 else False
        except KeyboardInterrupt:
            self.quit()
            return False  # Return False on interruption/error
        finally:
            # Cleanup
            if self.window:
                self.window.close()
            self.app.quit()

    def quit(self):
        if self.window:
            self.window.close()
        self.app.quit()


if __name__ == "__main__":
    sys.argv += ["--logging.file=false", "--logging.level=1"]
    sys.exit(RegionChanger(*sys.argv)())