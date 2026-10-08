"""JSON command-line interface; importing this module never imports the GUI."""
import argparse
import json
import sys

import core


def main(argv=None):
    # Frozen Windows executables do not reliably honor PYTHONIOENCODING.
    # JSON over pipes always uses UTF-8, independent of the console code page.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='WetBulb Calculator (Celsius, hPa, RH percent)')
    parser.add_argument('--version', action='version', version=core.tag)
    parser.add_argument('--mode', choices=('dewpoint', 'wetbulb', 'rh'), required=True,
                        help='Known input: dewpoint, wetbulb, or relative humidity')
    parser.add_argument('--temperature', type=float, required=True)
    parser.add_argument('--value', type=float, required=True)
    parser.add_argument('--pressure', type=float, default=1013.25)
    parser.add_argument('--method', choices=[f['name'] for f in core.FORMULAS])
    args = parser.parse_args(argv)
    try:
        if args.mode == 'dewpoint':
            results = core.calculate_wetbulb(args.value, args.temperature, args.value, args.pressure)
        elif args.mode == 'wetbulb':
            results = core.calculate_dewpoint(args.temperature, args.value, args.pressure)
        else:
            results = core.calculate_both(args.temperature, args.temperature, args.value, args.pressure)
        if args.method:
            results = [r for r in results if r['method'] == args.method]
        print(json.dumps({'version': core.tag, 'mode': args.mode, 'results': results},
                         ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
