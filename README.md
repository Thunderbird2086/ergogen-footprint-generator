# ergogen-footprint-generator
Generate ergogen footprints from KiCad footprint module 

## Overview
The Ergogen Footprint Generator is a Python tool designed to convert KiCad footprint modules into Ergogen-compatible footprints. This tool simplifies the process of integrating custom footprints into your Ergogen projects.

### Features
* Automated Conversion: Easily convert KiCad footprint modules to Ergogen format.
* Python-Based: Leverage the power and flexibility of Python for your conversion needs.
* Open Source: Licensed under GPL-3.0, ensuring freedom to use, modify, and distribute.

## Usage
To convert a KiCad footprint module to an Ergogen footprint, use the following command:
```bash
$ python3 fp-kicad8-to-ergogen.py -h
usage: fp-kicad8-to-ergogen.py [-h] [-o OUTDIR] [-v] file_or_directory

Parse KiCad .kicad_mod files.

positional arguments:
  file_or_directory     Path to the .kicad_mod file or directory to parse

options:
  -h, --help            show this help message and exit
  -o OUTDIR, --outdir OUTDIR
                        output directory, default is 'ergogen'
  -v, --verbose         verbose mode
```

Replace `file_or_directory` with the path to your KiCad footprint module and `OUTDIR` with the desired output path for the Ergogen footprint.<br>
If `OUTDIR` was omitted, `ergogen` will be used.

## Post Processing
Once the script dumps an Ergogen footprint, it’s almost ready to use. But it’s good to tweak it a bit. Let’s break it down.
```javascript
module.exports = {
  params: {
    designator: 'X',    // change it accordingly
    side: 'F',          // delete if not needed
    reversible: false,  // delete if not needed
    show_3d: false,     // delete if not needed
    P1: {type: 'net', value: 'P1'}, // undefined}, // change to undefined as needed
    P2: {type: 'net', value: 'P2'}, // undefined}, // change to undefined as needed
    ...
  },
  body: p => {
    const standard_opening = `(
```
In the params section, `designator` is the component ID on the PCB, so it’s better to change it to something like 'R' for a resistor, 'C' for a capacitor, etc.<br>
<br>
If a `padid` must be connected, it should be set to `undefined`, like this:
```javascript
  params: {
    ...
    P1: {type: 'net', value: 'P1'},         // P1 is optional
    P2: {type: 'net', value: undefined},    // P2 must be connected
    ...
  },
```
Here, `P2` must be connected while `P1` is optional.<br>
<br>
Finally, you can add more features like this:
```javascript
     ...

    let final = standard_opening;

    final += front_silkscreen;
    if (p.reversible || p.side == "F") { //  add items to the front side of the PCB
        final += front_pads;
        final += front_fabrication;
        final += front_mask;
        final += front_courtyard;
        final += front_paste;
    }

    final += pads;

    final += back_silkscreen;
    if (p.reversible || p.side == "B") { //  add items to the back side of the PCB
        final += back_pads;
        final += back_fabrication;
        final += back_mask;
        final += back_courtyard;
        final += back_paste;
    }

    final += edge_cuts;
    final += user_drawing;
    final += user_comments;
    final += user_eco1;     //  comment out if not needed
    final += user_eco2;     //  comment out if not needed

    if (p.show_3d) {
        final += model;
    }

    final += standard_closing;
    return final
  }
```

## Contributing
We welcome contributions! Please fork the repository and submit pull requests. For major changes, please open an issue first to discuss what you would like to change.

## License
This project is licensed under the GPL-3.0 License. See the LICENSE file for details.

Feel free to customize this draft to better fit your project’s specifics!

