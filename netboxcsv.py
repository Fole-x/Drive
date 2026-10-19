#!/usr/bin/env python3

import argparse
import csv
import ipaddress
import sys


def normalize_header(value: str) -> str:
    return value.strip().lower()


def convert_ip_to_address(ip_value: str, prefix_length: int) -> str:
    ip_value = ip_value.strip()

    if not ip_value:
        raise ValueError("Prázdná IP adresa")

    # Pokud už by náhodou obsahovala masku, ponecháme ji po validaci.
    if "/" in ip_value:
        interface = ipaddress.ip_interface(ip_value)
        return str(interface)

    ip = ipaddress.ip_address(ip_value)
    return f"{ip}/{prefix_length}"


def main():
    parser = argparse.ArgumentParser(
        description="Převod phpIPAM CSV exportu IP adres do NetBox CSV importu."
    )

    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Vstupní CSV z phpIPAM",
    )

    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Výstupní CSV pro NetBox",
    )

    parser.add_argument(
        "--prefix-length",
        type=int,
        default=24,
        help="Maska doplněná k IP adrese, výchozí 24",
    )

    parser.add_argument(
        "--skip-lines",
        type=int,
        default=4,
        help="Počet úvodních řádků k přeskočení, výchozí 4",
    )

    args = parser.parse_args()

    if not (0 <= args.prefix_length <= 128):
        print("Chyba: prefix-length musí být mezi 0 a 128.", file=sys.stderr)
        sys.exit(1)

    converted = 0
    skipped = 0
    errors = 0

    with open(args.input, "r", encoding="utf-8-sig", newline="") as infile, \
            open(args.output, "w", encoding="utf-8", newline="") as outfile:

        # Přeskočit úvodní nepotřebné řádky z phpIPAM exportu.
        for _ in range(args.skip_lines):
            next(infile, None)

        reader = csv.DictReader(infile, delimiter=";")

        if reader.fieldnames is None:
            print("Chyba: vstupní soubor nemá hlavičku.", file=sys.stderr)
            sys.exit(1)

        # Namapování hlaviček bez ohledu na mezery a velikost písmen.
        header_map = {
            normalize_header(name): name
            for name in reader.fieldnames
            if name is not None
        }

        required_columns = ["ip adresa", "popis", "hostname"]
        missing = [col for col in required_columns if col not in header_map]

        if missing:
            print(
                "Chyba: ve vstupním CSV chybí sloupce: "
                + ", ".join(missing),
                file=sys.stderr,
            )
            print(
                "Nalezené sloupce: "
                + ", ".join(reader.fieldnames),
                file=sys.stderr,
            )
            sys.exit(1)

        writer = csv.DictWriter(
            outfile,
            fieldnames=["address", "description", "dns_name", "status"],
            delimiter=";",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()

        for line_number, row in enumerate(reader, start=args.skip_lines + 2):
            ip_raw = row.get(header_map["ip adresa"], "").strip()
            description = row.get(header_map["popis"], "").strip()
            hostname = row.get(header_map["hostname"], "").strip()

            # Přeskočit úplně prázdné řádky.
            if not ip_raw and not description and not hostname:
                skipped += 1
                continue

            try:
                address = convert_ip_to_address(ip_raw, args.prefix_length)
            except ValueError as exc:
                errors += 1
                print(
                    f"Řádek {line_number}: přeskočeno, neplatná IP '{ip_raw}': {exc}",
                    file=sys.stderr,
                )
                continue

            writer.writerow({
                "address": address,
                "description": description,
                "dns_name": hostname,
                "status": "active",
            })

            converted += 1

    print(f"Hotovo.")
    print(f"Převedeno řádků: {converted}")
    print(f"Přeskočeno prázdných řádků: {skipped}")
    print(f"Chybné řádky: {errors}")

    if errors:
        sys.exit(2)


if __name__ == "__main__":
    main()
