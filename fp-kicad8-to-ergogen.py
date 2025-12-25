#!/usr/bin/env python3
import argparse
from enum import StrEnum
import logging
import os
from pyparsing import nested_expr, ParseResults
from typing import List, Tuple, Dict


class CustomFormatter(logging.Formatter):
    """
    Custom handler to log messages in different formats based on the level
    """

    def __init__(self, fmt=None, datefmt=None, style="%"):
        super().__init__(fmt, datefmt, style)
        self.formats = {
            logging.DEBUG: logging.Formatter(
                "%(asctime)s - %(levelname)8s - "
                "%(filename)s:%(lineno)d - %(message)s"
            ),
            logging.INFO: logging.Formatter("%(asctime)s - %(message)s"),
            logging.WARNING: logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s"
            ),
            logging.ERROR: logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s"
            ),
            logging.CRITICAL: logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s"
            ),
        }

    def format(self, record) -> str:
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


class ErgogenSyntaxConverter(object):
    """
    Converts KiCad mod file
    """

    def __init__(self):
        self.padnames = set()
        self.handlers = {
            "at": self._handle_at,
            "pad": self._handle_pad,
            "property": self._handle_property,
            "tstamp": self._handle_ignore,
            "uuid": self._handle_ignore,
        }

    def _handle_at(self, pos: List[str]) -> List[str]:
        """
        add ergogen rotation to position identifier
        """
        if len(pos) < 4:
            pos.append("${p.rot}")
        else:
            pos[3] = "${" + f"{pos[3]}" + " + p.rot}"
        return pos

    def _handle_pad(self, pad: List[str]) -> List[str]:
        """
        add prefix of 'P' if pad id starts with a number
        """
        pad_id = pad[1]
        if '""' == pad_id:
            return pad
        pad_id = pad_id.strip('"')
        modified_pad_name = f"P{pad_id}" if pad_id[0].isdigit() else pad_id
        _LOGGER.debug("%s - %s", pad, modified_pad_name)
        self.padnames.add(modified_pad_name)
        pad.append('${' + f'p.{modified_pad_name}' + '}')
        return pad

    def _handle_property(self, result: List[str]) -> List[str]:
        """
        add ergogen reference identifier
        """
        _LOGGER.debug(result)
        if '"Reference"' != result[1]:
            return result

        result[2] = '"${p.ref}"'
        result[3:] = [
            '(layer "${p.side}.SilkS")' if 'layer' in an_item else an_item for an_item in result[3:]]
        found = [an_item for an_item in result[3:] if 'hide' in an_item]
        if not found:
            result[3:] = [
                an_item for an_element in result[3:] for an_item in (an_element,
                'hide') if 'layer' in an_element or an_item == an_element ]
        result[3:] = [
            '${p.ref_hide}' if 'hide' in an_item else an_item for an_item in result[3:]]

        return result

    def _handle_ignore(self, result: List[str]) -> List[str]:
        """
        ignore field
        """
        return []

    def _rebuild_mod_data(self, parsed_data: ParseResults) -> str:
        """
        rebuild footprint item while adding ergogen expression if possible
        """
        result = []
        remapping = {
            '"REF**"': '"${p.ref}"',
            # '"F.Silks"': '"${p.side}.Silks"'
        }
        for item in parsed_data:
            _LOGGER.debug(item)
            if isinstance(item, ParseResults):
                result.append(self._rebuild_mod_data(item))
                continue
            item = item.replace("${", r"\${")
            _LOGGER.debug(item)
            result.append(remapping.get(item, item))
            _LOGGER.debug(result)

        handler = self.handlers.get(result[0], lambda x: x)

        result = handler(result)

        _LOGGER.debug(result)
        if not result:
            return ""

        return f"({result[0]} {' '.join(map(str, result[1:]))})"

    def _make_onelines(self, parsed_data: ParseResults) -> List[str]:
        """
        make footprint item as one line
        """
        result = []
        one_line = ""
        for item in parsed_data:
            if isinstance(item, ParseResults):
                if one_line:
                    result.append(one_line)
                    one_line = ""
                result.append(self._rebuild_mod_data(item))
                continue
            one_line += f" {item}"
        return result

    def convert(self, kicad_mod_file: str) -> Tuple[List[str], List[str]]:
        """
        converts KiCad footprint items into one line per each
        """
        try:
            _LOGGER.info("Processing: %s", kicad_mod_file)
            with open(kicad_mod_file) as file:
                mod_content = file.read()
            # Parse the content
            parsed_data = nested_expr("(", ")").parse_string(mod_content)
            _LOGGER.debug(parsed_data)
        except FileNotFoundError as e:
            _LOGGER.error("File not found: %s", e)

            return [], []

        # Flatten to the second level
        return self._make_onelines(parsed_data[0]), list(self.padnames)


class Layers(StrEnum):
    """
    KiCad layers
    """
    F_CU = "F.Cu"
    B_CU = "B.Cu"
    PAD = "pad"
    F_SILKS = "F.SilkS"
    B_SILKS = "B.SilkS"
    F_FAB = "F.Fab"
    B_FAB = "B.Fab"
    F_MASK = "F.Mask"
    B_MASK = "B.Mask"
    F_CRTYD = "F.CrtYd"
    B_CRTYD = "B.CrtYd"
    F_PASTE = "F.Paste"
    B_PASTE = "B.Paste"
    EDGE_CUTS = "Edge.Cuts"
    DWGS_USER = "Dwgs.User"
    CMTS_USER = "Cmts.User"
    ECO1_USER = "Eco1.User"
    ECO2_USER = "Eco2.User"
    MODEL = "model"  # model is not an actual layer though


class KiCadModSyntax(StrEnum):
    """
    mod syntax
    """
    OPENING = "Opening"
    CLOSING = "Closing"


class ErgogenFootPrint(object):
    def __init__(self, onelines: List[str], padnames: List[str]):
        self._onelines = onelines
        self._padnames = padnames

    def _filters_out(
        self, a_layer: str, onelines: List[str], options: List[str] = []
    ) -> Tuple[List[str], List[str]]:
        """
        fitlers out target layer with the given options.
        This is to avoid misaligned layer.
        """
        unprocessed, filtered = [], []
        for item in onelines:
            if a_layer not in item:
                unprocessed.append(item)
                continue
            if options and not any(an_option in item for an_option in options):
                _LOGGER.debug("options(%s) - item(%s)", options, item)
                unprocessed.append(item)
                continue
            filtered.append(item)
        return filtered, unprocessed

    def _get_layers(self, unprocessed: List[str]) -> Dict[str, List[str]]:
        """
        collect layers itmes
        """
        options = {
            Layers.F_CU: ["pad", "fp_line", "fp_poly", "fp_text"],
            Layers.B_CU: ["pad", "fp_line", "fp_poly", "fp_text"],
        }
        layers = {}
        for a_layer in Layers:
            filtered, unprocessed = self._filters_out(
                a_layer, unprocessed, options.get(a_layer, [])
            )
            if filtered:
                layers[a_layer] = filtered
        # assume uprocessd layers belong to opening
        layers[KiCadModSyntax.OPENING] = [an_item.replace(
            '(layer "F.Cu")', '(layer "${p.side}.Cu")').replace(
            '(layer "B.Cu")', '(layer "${p.side}.Cu")') for an_item in unprocessed]
        _LOGGER.debug(layers[KiCadModSyntax.OPENING])

        return layers

    def _make_code_blocks(self, layers: Dict[str, List[str]]) -> Dict[str, str]:
        """
        dump code blocks
        """
        target_layers = {
            KiCadModSyntax.OPENING: (  # it could be haeder
                "standard_opening",
                "(",
                "${p.at /* parametric position */}",
            ),
            Layers.F_SILKS: ("front_silkscreen", "", ""),
            Layers.F_CU: ("front_pads", "", ""),
            Layers.F_FAB: ("front_fabrication", "", ""),
            Layers.F_MASK: ("front_mask", "", ""),
            Layers.F_CRTYD: ("front_courtyard", "", ""),
            Layers.F_PASTE: ("front_paste", "", ""),
            Layers.PAD: ("pads", "", ""),
            Layers.B_SILKS: ("back_silkscreen", "", ""),
            Layers.B_CU: ("back_pads", "", ""),
            Layers.B_FAB: ("back_fabrication", "", ""),
            Layers.B_MASK: ("back_mask", "", ""),
            Layers.B_CRTYD: ("back_courtyard", "", ""),
            Layers.B_PASTE: ("back_paste", "", ""),
            Layers.EDGE_CUTS: ("edge_cuts", "", ""),
            Layers.DWGS_USER: ("user_drawing", "", ""),
            Layers.CMTS_USER: ("user_comments", "", ""),
            Layers.ECO1_USER: ("user_eco1", "", ""),
            Layers.ECO2_USER: ("user_eco2", "", ""),
            Layers.MODEL: ("model", "", ""),
            KiCadModSyntax.CLOSING: ("standard_closing", "", "    )"),
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

    def _dump_to_file(
        self, code_blocks: Dict[str, str], kicad_mod_file: str, outdir: str
    ) -> None:
        """
        dump an ergogen footprint file
        """
        filename, _ = os.path.splitext(os.path.basename(kicad_mod_file))
        output_file = os.path.join(outdir, f"{filename}.js")
        with open(output_file, "w") as f_out:
            f_out.write(
                "module.exports = {\n"
                "  params: {\n"
                "    designator: 'X',    // change it accordingly\n"
                "    side: 'F',          // delete if not needed\n"
                "    reversible: false,  // delete if not needed\n"
                "    show_3d: false,     // delete if not needed\n"
            )
            for a_padname in self._padnames:
                f_out.write(
                    (
                        f"    {a_padname}: "
                        "{type: 'net', value: "
                        f"'{a_padname}'"
                        "}, // undefined}, // change to undefined as needed\n"
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

    def _status(self, layers: Dict[str, List[str]]) -> None:
        """
        dump status
        """
        _LOGGER.debug("Flattened   :%6d", len(self._onelines))
        for layer_name, a_layer in layers.items():
            _LOGGER.debug("%-12s:%6d", layer_name, len(a_layer))

    def dump(self, kicad_mod_file: str, outdir: str) -> None:
        """
        dumps ergogen foot print
        """
        ergogen_layers = self._get_layers(self._onelines)
        self._status(ergogen_layers)
        code_blocks = self._make_code_blocks(ergogen_layers)
        self._dump_to_file(code_blocks, kicad_mod_file, outdir)


def convert_kicad_fp_to_ergogen_fp(kicad_mod_file: str, outdir: str) -> None:
    """
    It converts a kicad_mod file to ergogen footprint file
    """
    syntax_convertor = ErgogenSyntaxConverter()
    converted, padnames = syntax_convertor.convert(kicad_mod_file)

    ergogen_footprint = ErgogenFootPrint(converted, padnames)
    ergogen_footprint.dump(kicad_mod_file, outdir)


def process_directory(directory_path, outdir):
    """
    converts all kicad_mod files under the given directory
    to ergogen footprint file
    """
    for root, _, files in os.walk(directory_path):
        for file in files:
            if not file.endswith(".kicad_mod"):
                continue

            file_path = os.path.join(root, file)
            convert_kicad_fp_to_ergogen_fp(file_path, outdir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse KiCad .kicad_mod files.")
    parser.add_argument(
        "file_or_directory",
         help="Path to the .kicad_mod file or directory to parse"
    )

    parser.add_argument(
        "-o",
        "--outdir",
        default="ergogen",
        help="output directory, default is 'ergogen'",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="verbose mode")

    args = parser.parse_args()

    if args.verbose:
        _LOGGER.setLevel(logging.DEBUG)

    if not os.path.exists(args.outdir):
        os.mkdir(args.outdir)
        _LOGGER.info("'%s' has been created as it did not exist.", args.outdir)

    if os.path.isdir(args.file_or_directory):
        process_directory(args.file_or_directory, args.outdir)
    else:
        convert_kicad_fp_to_ergogen_fp(args.file_or_directory, args.outdir)
