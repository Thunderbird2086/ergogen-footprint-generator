#!/usr/bin/env python3
import argparse
import logging
import os
from pyparsing import nestedExpr, ParseResults
from typing import List, Tuple, Dict


class CustomFormatter(logging.Formatter):
    """
    Custom handler to log messages in different formats based on the level
    """
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        self.formats = {
            logging.DEBUG: logging.Formatter("%(asctime)s - %(levelname)8s - %(filename)s:%(lineno)d - %(message)s"),
            logging.INFO: logging.Formatter("%(asctime)s - %(message)s"),
            logging.WARNING: logging.Formatter('%(asctime)s - %(levelnae)s - %(message)s'),
            logging.ERROR: logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'),
            logging.CRITICAL: logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        }

    def format(self, record):
        formatter = self.formats.get(record.levelno)
        if formatter is None:
            formatter = self.formats[logging.INFO]
        return formatter.format(record)

def setup_logger() -> logging.Logger:
    """
    set up custom logger
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    ch = logging.StreamHandler()
    ch.setFormatter(CustomFormatter())

    logger.addHandler(ch)
    return logger


_LOGGER = setup_logger()


def parse_kicad_mod(kicad_mod_file: str, outdir: str) -> None:
    """
    It converts a kicad_mod file to ergogen footprint file
    """
    try:
        _LOGGER.info("Processing: %s", kicad_mod_file)
        params = set()
        with open(kicad_mod_file) as file:
            mod_content = file.read()
        # Parse the content
        parsed_data = nestedExpr("(", ")").parseString(mod_content)
        _LOGGER.debug(parsed_data)
    except FileNotFoundError as e:
        _LOGGER.error("File not found: %s", e)
        return

    def modify_rotation(pos: List[str]) -> List[str]:
        if len(pos) < 4:
            pos.append("${p.rot}")
        else:
            pos[3] = "${" + f"{pos[3]}" + " + p.rot}"
        return pos

    def modify_padname(pad: List[str]) -> List[str]:
        """
        add prefix of 'P' if pad id starts with a number
        """
        pad_id = pad[1]
        if '""' == pad_id:
            return pad
        pad_id = pad_id.strip('"')
        modified_pad_name = f"P{pad_id}" if pad_id[0].isdigit() else pad_id
        _LOGGER.debug("%s - %s", pad, modified_pad_name)
        params.add(modified_pad_name)
        pad.append("${" + f"p.{modified_pad_name}" + "}")
        return pad

    def rebuild_mod_data(parsed_data: ParseResults) -> str:
        result = []
        remapping = {
            '"REF**"': '"${p.ref}"',
            # '"F.Silks"': '"${p.side}.Silks"'
        }
        for item in parsed_data:
            if isinstance(item, ParseResults):
                result.append(rebuild_mod_data(item))
                continue
            item = item.replace("${", "\${")
            result.append(remapping.get(item, item))
        if "at" == result[0]:
            result = modify_rotation(result)
        elif "pad" == result[0]:
            result = modify_padname(result)
        _LOGGER.debug(result)
        return f"({result[0]} {' '.join(map(str, result[1:]))})"

    def flatten_to_second_level(parsed_data: ParseResults) -> List[str]:
        # Function to flatten only up to the second level
        result = []
        one_line = ""
        for item in parsed_data:
            if isinstance(item, ParseResults):
                if one_line:
                    result.append(one_line)
                    one_line = ""
                result.append(rebuild_mod_data(item))
                continue
            one_line += f" {item}"
        return result

    def filters_out(
        a_target: str, flattened: List[str], options: List[str] = []
    ) -> Tuple[List[str], List[str]]:
        unprocessed, filtered = [], []
        for item in flattened:
            if a_target not in item:
                unprocessed.append(item)
                continue
            if options and not any(an_option in item for an_option in options):
                _LOGGER.debug("options(%s) - item(%s)", options, item)
                unprocessed.append(item)
                continue
            filtered.append(item)
        return filtered, unprocessed

    def get_layers(flattened: List[str]) -> Dict[str, List[str]]:
        target_layers = [
            "F.Cu",
            "B.Cu",
            "pad",
            "F.SilkS",
            "B.SilkS",
            "F.Fab",
            "B.Fab",
            "F.Mask",
            "B.Mask",
            "F.CrtYd",
            "B.CrtYd",
            "F.Paste",
            "B.Paste",
            "Edge.Cuts",
            "Dwgs.User",
            "Cmts.User",
            "Eco1.User",
            "Eco2.User",
            "model",
        ]
        options = {
            "F.Cu": ["pad", "fp_line", "fp_poly", "fp_text"],
            "B.Cu": ["pad", "fp_line", "fp_poly", "fp_text"],
        }
        layers = {}
        for a_layer in target_layers:
            filtered, flattened = filters_out(
                a_layer, flattened, options.get(a_layer, [])
            )
            layers[a_layer] = filtered
        layers["Unprocessed"] = flattened
        return layers

    def print_stats(layers: Dict[str, List[str]], flattened: List[str]) -> None:
        if _LOGGER.getEffectiveLevel() > logging.DEBUG:
            return
        _LOGGER.info("Flattened   :%6d", len(flattened))
        for layer_name, a_layer in layers.items():
            _LOGGER.info("%-12s:%6d", layer_name, len(a_layer))
        _LOGGER.info("Unprocessed :%6d", len(layers["Unprocessed"]))

    def get_code_blocks(layers: Dict[str, List[str]]) -> Dict[str, str]:
        target_layers = {
            "Unprocessed": (
                "standard_opening",
                "(",
                "${p.at /* parametric position */}",
            ),
            "F.Cu": ("front_pads", "", ""),
            "F.SilkS": ("front_silkscreen", "", ""),
            "F.Fab": ("front_fabrication", "", ""),
            "F.Mask": ("front_mask", "", ""),
            "F.CrtYd": ("front_courtyard", "", ""),
            "F.Paste": ("front_paste", "", ""),
            "pad": ("pads", "", ""),
            "B.Cu": ("back_pads", "", ""),
            "B.SilkS": ("back_silkscreen", "", ""),
            "B.Fab": ("back_fabrication", "", ""),
            "B.Mask": ("back_mask", "", ""),
            "B.CrtYd": ("back_courtyard", "", ""),
            "B.Paste": ("back_paste", "", ""),
            "Edge.Cuts": ("edge_cuts", "", ""),
            "Dwgs.User": ("user_drawing", "", ""),
            "Cmts.User": ("user_comments", "", ""),
            "Eco1.User": ("user_eco1", "", ""),
            "Eco2.User": ("user_eco2", "", ""),
            "model": ("model", "", ""),
            "Closing": ("standard_closing", "", "    )\n"),
        }
        layers_code_block = {}
        for layer_name in target_layers:
            _LOGGER.debug("%-12s-----", layer_name)
            const_variable, pre_block, post_block = target_layers[layer_name]
            code_block = f"    const {const_variable} = `{pre_block}\n"
            a_layer = layers.get(layer_name, [])
            for an_element in a_layer:
                code_block += f"        {an_element}\n"
                _LOGGER.debug("    %s", an_element)
            if post_block:
                code_block += f"        {post_block}\n"
            code_block += "    `\n"
            layers_code_block[const_variable] = code_block
        return layers_code_block

    def dump_ergogen_footprint(
        codeblock: Dict[str, str], kicad_mod_file: str, outdir: str
    ) -> None:
        filename, _ = os.path.splitext(os.path.basename(kicad_mod_file))
        output_file = os.path.join(outdir, f"{filename}.js")
        with open(output_file, "w") as f_out:
            f_out.write(
                "module.exports = {\n"
                "  params: {\n"
                "    designator: 'X',    // change it accordingly\n"
                "    side: 'F',          // delete if not needed\n"
                "    reversible: false,  // delete if not needed\n"
            )
            for a_param in params:
                f_out.write(
                    (
                        f"    {a_param}: "
                        "{type: 'net', value: "
                        f"'{a_param}'"
                        "}, // undefined, // change to undefined as needed\n"
                    )
                )
            f_out.write("  },\n" "  body: p => {\n")
            for _, code_block in code_blocks.items():
                f_out.write(code_block)
            const_variables = list(code_blocks.keys())
            f_out.write(f"    let final = {const_variables[0]};\n")
            for a_const in const_variables[1:]:
                f_out.write(f"    final += {a_const};\n")
            f_out.write("\n" "    return final\n" "  }\n" "}")
        _LOGGER.info("dumped ergogen footprint, '%s'", output_file)

    # Flatten to the second level
    flattened = flatten_to_second_level(parsed_data[0])

    layers = get_layers(flattened)
    print_stats(layers, flattened)
    code_blocks = get_code_blocks(layers)
    dump_ergogen_footprint(code_blocks, kicad_mod_file, outdir)


def process_directory(directory_path, outdir):
    for root, _, files in os.walk(directory_path):
        for file in files:
            if not file.endswith(".kicad_mod"):
                continue

            file_path = os.path.join(root, file)
            parse_kicad_mod(file_path, outdir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse KiCad .kicad_mod files.")
    parser.add_argument(
        "file_or_directory", help="Path to the .kicad_mod file or directory to parse"
    )

    parser.add_argument("-o", "--outdir", default="ergogen", help="output directory")

    parser.add_argument("-v", "--verbose", action="store_true", help="verbose mode")

    args = parser.parse_args()

    if args.verbose:
        _LOGGER.setLevel(logging.DEBUG)

    if not os.path.exists(args.outdir):
        os.mkdir(args.outdir)
        _LOGGER.info("'%s' has been created as it did not exist.", args.outdir)

    if os.path.isdir(args.file_or_directory):
        process_directory(args.file_or_directory, args.outdir)
    else:
        parse_kicad_mod(args.file_or_directory, args.outdir)