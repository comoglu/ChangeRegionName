# ChangeRegionName

A SeisComP GUI application for managing and updating event region names based on nearby locations and custom formats.

## Overview

ChangeRegionName is a Python-based tool that integrates with the SeisComP framework to provide an intuitive interface for viewing and modifying seismic event region names. The application allows users to:

- Fetch events by ID and view/edit their region descriptions
- Find nearby geographical locations relative to an event's coordinates
- Generate region names using customizable formatting templates
- Filter locations by type and distance
- Apply custom region names manually

## Features

### Region Editor Tab
- Fetch event information using event ID
- View and edit the current region name
- Display event coordinates (latitude/longitude)
- Apply custom region names
- Keyboard shortcuts for common operations (F5 to fetch, F2 to edit, Ctrl+S to save)

### Location Finder Tab
- Search for nearby locations based on event coordinates
- Customize search parameters (max distance, max locations)
- Select direction precision (4, 8, or 16 cardinal directions)
- Filter hamlet-type locations
- View distance and direction information
- Preview region names using different format templates
- Select and apply region names to events

## Requirements

- SeisComP installation (with Python bindings)
- PyQt5
- Python 3.x
- Environment variable `EATWS_SHARE_FOLDER` pointing to the folder containing `locations.json`

## Installation

1. Clone this repository:
   ```
   git clone git@github.com:comoglu/ChangeRegionName.git
   ```

2. Ensure you have the required dependencies installed in your SeisComP Python environment.

3. Make the script executable:
   ```
   chmod +x ChangeRegionName.py
   ```

4. Set up the `EATWS_SHARE_FOLDER` environment variable to point to the directory containing the `locations.json` file:
   ```
   export EATWS_SHARE_FOLDER="/path/to/directory"
   ```

## Usage

Run the application:
```
./ChangeRegionName.py
```

### Basic Workflow

1. Enter an event ID in the Region Editor tab and press Enter or click "Fetch Region"
2. View the current region name and coordinates
3. Click "Show Nearby Locations" to search for nearby geographical locations
4. In the Location Finder tab, adjust search parameters if needed
5. Select a location from the results table
6. Choose a format template for the region name
7. Click "Use This Region Name" to apply it to the event
8. Back in the Region Editor tab, click "Save Changes" to update the event in SeisComP

### Keyboard Shortcuts

- F5: Fetch event information
- F2: Enable region name editing
- Ctrl+S: Save changes
- Ctrl+Q: Close application

## Location Data

The application uses a JSON file containing location information with the following structure:
```json
[
  {
    "id": 123,
    "type": "city",
    "name": "Example City",
    "lat": 12.345,
    "lon": 67.890,
    "population": 50000,
    "admin_level": "admin_level",
    "state": "State Name",
    "country": "Country Name",
    "postcode": "12345",
    "state_full": "Full State Name"
  },
  ...
]
```

## License

Free to copy and distribute.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For questions and support, please [open an issue](https://github.com/comoglu/ChangeRegionName/issues) in the GitHub repository.