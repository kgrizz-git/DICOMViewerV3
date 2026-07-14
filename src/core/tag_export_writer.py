"""
DICOM Tag Export Writer

Provides filename generation and file writing (Excel, CSV, UTF-8 text) for DICOM tag
exports. CSV uses comma-separated fields; text exports use the same columns as tab-
separated values (``.txt``) for easy viewing and paste into spreadsheets.
This module is pure logic with no Qt dependency.
"""

import csv
from pathlib import Path
from typing import Any

from pydicom.dataset import Dataset

from core.dicom_parser import DICOMParser
from core.spreadsheet_safety import SafeCsvWriter, neutralize_spreadsheet_value
from core.tag_export_catalog import missing_tag_export_display_fields


def _tag_number_for_export(tag_str: str, tag_data: dict[str, Any]) -> str:
    """The identifier written to the "Tag Number" column.

    ``tag_data['tag']`` is the *canonical* tag, which for a nested sequence leaf
    discards the path — two leaves under different sequences would both export as
    ``(0008, 0104)``, re-creating in the spreadsheet exactly the ambiguity path keys
    exist to remove. So nested rows (``depth > 0``) export their full path key instead.

    Root-level rows export the canonical tag, which is identical to their key.
    """
    if tag_data.get('depth', 0):
        return tag_str
    return tag_data.get('tag', tag_str)


def generate_default_filename(
    studies: dict[str, dict[str, list[Dataset]]],
    selected_series: dict[str, dict[str, list[int]]],
) -> str:
    """Generate a default filename for tag export (Excel format)."""
    first_study_uid = next(iter(selected_series.keys()))
    first_series_uid = next(iter(selected_series[first_study_uid].keys()))
    first_instance_idx = selected_series[first_study_uid][first_series_uid][0]
    first_dataset = studies[first_study_uid][first_series_uid][first_instance_idx]

    modality = getattr(first_dataset, 'Modality', 'Unknown')
    accession = getattr(first_dataset, 'AccessionNumber', 'Unknown')
    return f"{modality} DICOM Tag Export {accession}.xlsx"


def write_excel_file(
    file_path: str,
    variation_analysis: dict[str, dict[str, list[str]]],
    studies: dict[str, dict[str, list[Dataset]]],
    selected_series: dict[str, dict[str, list[int]]],
    selected_tags: list[str],
    include_private: bool,
    include_missing_selected_tags: bool = True,
    include_sequences: bool = False,
) -> None:
    """Write selected tags to an Excel file with per-instance export for varying tags.

    ``include_sequences`` (default False) mirrors
    :meth:`~core.dicom_parser.DICOMParser.get_all_tags`'s flag: off reproduces the
    historical scalar-only export byte-for-byte; on lets a selected SQ tag resolve
    to its single-cell summary value (item count, or the compact code summary for
    code sequences) instead of always falling through to the missing-tag row.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        raise ImportError(  # noqa: B904 - the ModuleNotFoundError adds nothing here
            "openpyxl library is required for Excel export. "
            "Install it with: pip install openpyxl"
        )

    wb = Workbook()
    default_ws = wb.active
    if default_ws is not None:
        wb.remove(default_ws)  # Remove default sheet

    # Create one sheet per study
    for study_uid, series_dict in selected_series.items():
        first_series_uid = next(iter(series_dict.keys()))
        first_instance_idx = series_dict[first_series_uid][0]
        first_dataset = studies[study_uid][first_series_uid][first_instance_idx]
        study_desc = getattr(first_dataset, 'StudyDescription', 'Study')
        # Sanitize sheet name (max 31 chars, no special chars)
        sheet_name = study_desc[:31].replace('/', '-').replace('\\', '-').replace(':', '-')

        ws = wb.create_sheet(title=sheet_name)

        # Write header
        ws['A1'] = 'Instance'
        ws['B1'] = 'Tag Number'
        ws['C1'] = 'Name'
        ws['D1'] = 'Value'
        for cell in ('A1', 'B1', 'C1', 'D1'):
            ws[cell].font = Font(bold=True)

        row = 2

        # Export each selected series
        for series_uid, instance_indices in series_dict.items():
            datasets = studies[study_uid][series_uid]
            if not datasets:
                continue

            first_ds = datasets[0]

            # Write series header
            series_num = getattr(first_ds, 'SeriesNumber', '')
            series_desc = getattr(first_ds, 'SeriesDescription', 'Unknown')
            ws[f'A{row}'] = neutralize_spreadsheet_value(f"Series {series_num}: {series_desc}")
            ws[f'A{row}'].font = Font(bold=True, italic=True)
            ws.merge_cells(f'A{row}:D{row}')
            row += 1

            analysis = variation_analysis.get(
                series_uid, {'varying_tags': [], 'constant_tags': selected_tags}
            )
            varying_tags = analysis['varying_tags']
            constant_tags = analysis['constant_tags']

            # Export constant tags (once per series, using first instance)
            if constant_tags and instance_indices:
                first_instance_idx = instance_indices[0]
                if first_instance_idx < len(datasets):
                    dataset = datasets[first_instance_idx]
                    parser = DICOMParser(dataset)
                    all_tags = parser.get_all_tags(
                        include_private=include_private, include_sequences=include_sequences
                    )

                    for tag_str in constant_tags:
                        if tag_str in all_tags:
                            tag_data = all_tags[tag_str]
                            ws[f'A{row}'] = 'All'  # Indicates all instances
                            ws[f'B{row}'] = neutralize_spreadsheet_value(
                                _tag_number_for_export(tag_str, tag_data)
                            )
                            ws[f'C{row}'] = neutralize_spreadsheet_value(tag_data.get('name', ''))

                            value = tag_data.get('value', '')
                            if isinstance(value, list):
                                value_str = ', '.join(str(v) for v in value)
                            else:
                                value_str = str(value)
                            ws[f'D{row}'] = neutralize_spreadsheet_value(value_str)

                            row += 1
                        elif include_missing_selected_tags:
                            tag_num, tag_name = missing_tag_export_display_fields(tag_str)
                            ws[f'A{row}'] = 'All'
                            ws[f'B{row}'] = neutralize_spreadsheet_value(tag_num or tag_str)
                            ws[f'C{row}'] = neutralize_spreadsheet_value(tag_name)
                            ws[f'D{row}'] = ''
                            row += 1

            # Export varying tags (per instance)
            if varying_tags:
                for instance_idx in instance_indices:
                    if instance_idx >= len(datasets):
                        continue

                    dataset = datasets[instance_idx]
                    parser = DICOMParser(dataset)
                    all_tags = parser.get_all_tags(
                        include_private=include_private, include_sequences=include_sequences
                    )

                    instance_num = getattr(dataset, 'InstanceNumber', None)
                    instance_id = (
                        f"Instance {instance_num}"
                        if instance_num is not None
                        else f"Instance {instance_idx + 1}"
                    )

                    for tag_str in varying_tags:
                        if tag_str in all_tags:
                            tag_data = all_tags[tag_str]
                            ws[f'A{row}'] = instance_id
                            ws[f'B{row}'] = neutralize_spreadsheet_value(
                                _tag_number_for_export(tag_str, tag_data)
                            )
                            ws[f'C{row}'] = neutralize_spreadsheet_value(tag_data.get('name', ''))

                            value = tag_data.get('value', '')
                            if isinstance(value, list):
                                value_str = ', '.join(str(v) for v in value)
                            else:
                                value_str = str(value)
                            ws[f'D{row}'] = neutralize_spreadsheet_value(value_str)

                            row += 1
                        elif include_missing_selected_tags:
                            tag_num, tag_name = missing_tag_export_display_fields(tag_str)
                            ws[f'A{row}'] = instance_id
                            ws[f'B{row}'] = neutralize_spreadsheet_value(tag_num or tag_str)
                            ws[f'C{row}'] = neutralize_spreadsheet_value(tag_name)
                            ws[f'D{row}'] = ''
                            row += 1

            # Add blank row between series
            row += 1

    # Adjust column widths
    for sheet in wb.worksheets:
        sheet.column_dimensions['A'].width = 15
        sheet.column_dimensions['B'].width = 15
        sheet.column_dimensions['C'].width = 40
        sheet.column_dimensions['D'].width = 60

    wb.save(file_path)


def _write_tag_export_sheet_rows(
    writer: Any,
    study_uid: str,
    series_dict: dict[str, list[int]],
    studies: dict[str, dict[str, list[Dataset]]],
    variation_analysis: dict[str, dict[str, list[str]]],
    selected_tags: list[str],
    include_private: bool,
    include_missing_selected_tags: bool,
    include_sequences: bool = False,
) -> None:
    """Write one study's tag rows using *writer* (``csv.writer`` with any dialect).

    ``include_sequences`` (default False) is forwarded to
    :meth:`~core.dicom_parser.DICOMParser.get_all_tags` — see :func:`write_excel_file`.
    """
    writer.writerow(['Instance', 'Tag Number', 'Name', 'Value'])

    for series_uid, instance_indices in series_dict.items():
        datasets = studies[study_uid][series_uid]
        if not datasets:
            continue

        first_ds = datasets[0]

        series_num = getattr(first_ds, 'SeriesNumber', '')
        series_desc = getattr(first_ds, 'SeriesDescription', 'Unknown')
        writer.writerow([f"Series {series_num}: {series_desc}", '', '', ''])

        analysis = variation_analysis.get(
            series_uid, {'varying_tags': [], 'constant_tags': selected_tags}
        )
        varying_tags = analysis['varying_tags']
        constant_tags = analysis['constant_tags']

        if constant_tags and instance_indices:
            first_instance_idx = instance_indices[0]
            if first_instance_idx < len(datasets):
                dataset = datasets[first_instance_idx]
                parser = DICOMParser(dataset)
                all_tags = parser.get_all_tags(
                    include_private=include_private, include_sequences=include_sequences
                )

                for tag_str in constant_tags:
                    if tag_str in all_tags:
                        tag_data = all_tags[tag_str]
                        tag_num = _tag_number_for_export(tag_str, tag_data)
                        tag_name = tag_data.get('name', '')

                        value = tag_data.get('value', '')
                        if isinstance(value, list):
                            value_str = ', '.join(str(v) for v in value)
                        else:
                            value_str = str(value)

                        writer.writerow(['All', tag_num, tag_name, value_str])
                    elif include_missing_selected_tags:
                        tag_num, tag_name = missing_tag_export_display_fields(tag_str)
                        writer.writerow(['All', tag_num or tag_str, tag_name, ''])

        if varying_tags:
            for instance_idx in instance_indices:
                if instance_idx >= len(datasets):
                    continue

                dataset = datasets[instance_idx]
                parser = DICOMParser(dataset)
                all_tags = parser.get_all_tags(
                    include_private=include_private, include_sequences=include_sequences
                )

                instance_num = getattr(dataset, 'InstanceNumber', None)
                instance_id = (
                    f"Instance {instance_num}"
                    if instance_num is not None
                    else f"Instance {instance_idx + 1}"
                )

                for tag_str in varying_tags:
                    if tag_str in all_tags:
                        tag_data = all_tags[tag_str]
                        tag_num = _tag_number_for_export(tag_str, tag_data)
                        tag_name = tag_data.get('name', '')

                        value = tag_data.get('value', '')
                        if isinstance(value, list):
                            value_str = ', '.join(str(v) for v in value)
                        else:
                            value_str = str(value)

                        writer.writerow([instance_id, tag_num, tag_name, value_str])
                    elif include_missing_selected_tags:
                        tag_num, tag_name = missing_tag_export_display_fields(tag_str)
                        writer.writerow([instance_id, tag_num or tag_str, tag_name, ''])

        writer.writerow([])


def write_csv_files(
    base_file_path: str,
    variation_analysis: dict[str, dict[str, list[str]]],
    studies: dict[str, dict[str, list[Dataset]]],
    selected_series: dict[str, dict[str, list[int]]],
    selected_tags: list[str],
    include_private: bool,
    include_missing_selected_tags: bool = True,
    include_sequences: bool = False,
) -> list[Path]:
    """
    Write selected tags to CSV files (one per study) with per-instance export for varying tags.

    ``include_sequences`` (default False) is forwarded to
    :meth:`~core.dicom_parser.DICOMParser.get_all_tags` — see :func:`write_excel_file`.

    Returns:
        List of created file paths.
    """
    base_path = Path(base_file_path)
    base_name = base_path.stem
    base_dir = base_path.parent
    exported_files: list[Path] = []

    for study_uid, series_dict in selected_series.items():
        first_series_uid = next(iter(series_dict.keys()))
        first_instance_idx = series_dict[first_series_uid][0]
        first_dataset = studies[study_uid][first_series_uid][first_instance_idx]
        study_desc = getattr(first_dataset, 'StudyDescription', 'Study')
        safe_study_desc = study_desc.replace('/', '-').replace('\\', '-').replace(':', '-')[:50]

        if len(selected_series) > 1:
            csv_filename = f"{base_name}_{safe_study_desc}.csv"
        else:
            csv_filename = f"{base_name}.csv"

        csv_path = base_dir / csv_filename

        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = SafeCsvWriter(csv.writer(csvfile))
            _write_tag_export_sheet_rows(
                writer,
                study_uid,
                series_dict,
                studies,
                variation_analysis,
                selected_tags,
                include_private,
                include_missing_selected_tags,
                include_sequences,
            )

        exported_files.append(csv_path)

    return exported_files


def write_txt_files(
    base_file_path: str,
    variation_analysis: dict[str, dict[str, list[str]]],
    studies: dict[str, dict[str, list[Dataset]]],
    selected_series: dict[str, dict[str, list[int]]],
    selected_tags: list[str],
    include_private: bool,
    include_missing_selected_tags: bool = True,
    include_sequences: bool = False,
) -> list[Path]:
    """
    Write selected tags to UTF-8 text files (one per study), tab-separated columns,
    same row layout as :func:`write_csv_files`.

    ``include_sequences`` (default False) is forwarded to
    :meth:`~core.dicom_parser.DICOMParser.get_all_tags` — see :func:`write_excel_file`.

    Returns:
        List of created file paths (``.txt``).
    """
    base_path = Path(base_file_path)
    base_name = base_path.stem
    base_dir = base_path.parent
    exported_files: list[Path] = []

    for study_uid, series_dict in selected_series.items():
        first_series_uid = next(iter(series_dict.keys()))
        first_instance_idx = series_dict[first_series_uid][0]
        first_dataset = studies[study_uid][first_series_uid][first_instance_idx]
        study_desc = getattr(first_dataset, 'StudyDescription', 'Study')
        safe_study_desc = study_desc.replace('/', '-').replace('\\', '-').replace(':', '-')[:50]

        if len(selected_series) > 1:
            txt_filename = f"{base_name}_{safe_study_desc}.txt"
        else:
            txt_filename = f"{base_name}.txt"

        txt_path = base_dir / txt_filename

        with open(txt_path, 'w', newline='', encoding='utf-8') as txtfile:
            writer = SafeCsvWriter(csv.writer(txtfile, delimiter='\t'))
            _write_tag_export_sheet_rows(
                writer,
                study_uid,
                series_dict,
                studies,
                variation_analysis,
                selected_tags,
                include_private,
                include_missing_selected_tags,
                include_sequences,
            )

        exported_files.append(txt_path)

    return exported_files
