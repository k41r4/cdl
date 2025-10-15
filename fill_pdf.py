import argparse
from pathlib import Path
from typing import Dict, List

from pypdf import PdfReader, PdfWriter


def parse_tab_delimited_input(input_data_string: str) -> Dict[str, str]:
	"""
	Parse a tab-delimited string into a structured mapping for form filling.

	This mapping reflects the provided index positions. Adjust indices to match
	your actual data layout when needed.
	"""
	parts: List[str] = input_data_string.split("\t")
	# Guard against short inputs to avoid IndexError; missing values become ""
	def safe(parts_list: List[str], index: int) -> str:
		return parts_list[index] if index < len(parts_list) else ""

	return {
		"id_class": safe(parts, 0),
		"ten_hv": safe(parts, 4),
		"id_hv": safe(parts, 3),
		"ngay_bat_dau": safe(parts, 7),
		"id_gs": safe(parts, 9),
		"ten_gs": safe(parts, 10),
		"san_pham": safe(parts, 13),
		"quan_ly_lop": safe(parts, 17),
		"cvcm_phu_trach": safe(parts, 18),
	}


def build_pdf_field_values(data_map: Dict[str, str]) -> Dict[str, str]:
	"""
	Return mapping from PDF field names to values to fill.

	Update keys here to match the actual field names in your PDF template.
	"""
	return {
		"ma_lop": data_map.get("id_class", ""),
		"ma_hoc_vien": data_map.get("id_hv", ""),
		"ho_ten_hv": data_map.get("ten_hv", ""),
		"ngay_bat_dau_cong_tac": data_map.get("ngay_bat_dau", ""),
		"ma_gia_su": data_map.get("id_gs", ""),
		"ho_ten_gs": data_map.get("ten_gs", ""),
		"mon_lop": data_map.get("san_pham", ""),
		"quan_ly_lop_phu_trach": data_map.get("quan_ly_lop", ""),
		"co_van_chuyen_mon": data_map.get("cvcm_phu_trach", ""),
		"ten_gia_su_ky_ten": data_map.get("ten_gs", ""),
	}


def set_need_appearances(writer: PdfWriter) -> None:
	"""
	Hint PDF viewers to regenerate appearances so filled values render.

	Some viewers require the AcroForm's /NeedAppearances flag to be true.
	"""
	try:
		root = writer._root_object  # type: ignore[attr-defined]
		if "/AcroForm" in root:
			acroform = root["/AcroForm"]
		else:
			acroform = writer._add_object({})  # type: ignore[attr-defined]
			root.update({"/AcroForm": acroform})
		# Set /NeedAppearances true
		acroform.update({"/NeedAppearances": True})
	except Exception:
		# Non-fatal; continue without flag if API changes
		pass


def list_form_fields(template_pdf_path: Path) -> Dict[str, str]:
	reader = PdfReader(str(template_pdf_path))
	# Prefer text fields API if available
	try:
		fields = reader.get_form_text_fields()  # type: ignore[attr-defined]
		return {name: (value if value is not None else "") for name, value in fields.items()}
	except Exception:
		pass
	try:
		fields2 = reader.get_fields()  # type: ignore[attr-defined]
		return {name: (field.get("/V", "") if isinstance(field, dict) else "") for name, field in (fields2 or {}).items()}
	except Exception:
		return {}


def fill_pdf_form(input_data_string: str, template_pdf_path: Path, output_pdf_path: Path) -> None:
	data_map = parse_tab_delimited_input(input_data_string)
	fields_to_fill = build_pdf_field_values(data_map)

	reader = PdfReader(str(template_pdf_path))
	writer = PdfWriter()

	for page in reader.pages:
		writer.add_page(page)

	# Set appearances to improve rendering of filled values
	set_need_appearances(writer)

	# Update fields on all pages to be safe
	for page_index in range(len(writer.pages)):
		writer.update_page_form_field_values(writer.pages[page_index], fields_to_fill)

	with output_pdf_path.open("wb") as out_fp:
		writer.write(out_fp)


def build_cli() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Fill and inspect PDF AcroForm templates.")
	subparsers = parser.add_subparsers(dest="command", required=True)

	# list-fields command
	list_cmd = subparsers.add_parser("list-fields", help="List form field names and current values")
	list_cmd.add_argument("template", type=Path, help="Path to template PDF")

	# fill command
	f_fill = subparsers.add_parser("fill", help="Fill a PDF template from a tab-delimited string")
	f_fill.add_argument("template", type=Path, help="Path to template PDF")
	f_fill.add_argument("output", type=Path, help="Path to save the filled PDF")
	f_fill.add_argument("--data", required=False, help="Tab-delimited input string")
	f_fill.add_argument("--data-file", type=Path, required=False, help="Path to a text file containing the tab-delimited string")

	return parser


def main() -> None:
	parser = build_cli()
	args = parser.parse_args()

	if args.command == "list-fields":
		fields = list_form_fields(args.template)
		if not fields:
			print("No form fields detected.")
			return
		for name, value in fields.items():
			print(f"{name}\t{value}")
		return

	if args.command == "fill":
		if args.data is None and args.data_file is None:
			parser.error("Provide --data or --data-file for fill command")
		if args.data_file is not None:
			input_string = args.data_file.read_text(encoding="utf-8").strip()
		else:
			input_string = args.data
		fill_pdf_form(input_string, args.template, args.output)
		print(f"Đã tạo file PDF thành công tại: {args.output}")
		return


if __name__ == "__main__":
	main()


