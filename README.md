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

## Contributing
We welcome contributions! Please fork the repository and submit pull requests. For major changes, please open an issue first to discuss what you would like to change.

## License
This project is licensed under the GPL-3.0 License. See the LICENSE file for details.

Feel free to customize this draft to better fit your project’s specifics!

