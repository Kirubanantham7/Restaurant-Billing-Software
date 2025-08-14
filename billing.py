from fpdf import FPDF
from datetime import datetime
import csv
import json
import os

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "DejaVuSans.ttf")

def generate_pdf_bill(order_id, items, totals, save_path):
    pdf = FPDF()
    pdf.add_page()

    # Add Unicode font (₹ symbol support)
    if not os.path.exists(FONT_FILE):
        raise FileNotFoundError(f"Font file '{FONT_FILE}' not found. Please place it in the same directory as this script.")

    pdf.add_font('DejaVu', "", FONT_FILE, uni=True)
    pdf.set_font('DejaVu', "", 12)

    pdf.cell(200, 10, txt="Kiruba Restaurant - Bill", ln=1, align="C")
    pdf.cell(200, 10, txt=f"Order ID: {order_id}", ln=2, align="C")
    pdf.cell(200, 10, txt=f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=3, align="C")
    pdf.ln(10)

    for item in items:
        name = item['name']
        qty = item['quantity']
        price = item['price']
        total = qty * price
        pdf.cell(200, 10, txt=f"{name} x{qty} = ₹{total:.2f}", ln=1)

    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Subtotal: ₹{totals['subtotal']}", ln=1)
    pdf.cell(200, 10, txt=f"Discount: ₹{totals['discount']}", ln=1)
    pdf.cell(200, 10, txt=f"Tax: ₹{totals['tax']}", ln=1)
    pdf.set_font('DejaVu', "", 12)
    pdf.cell(200, 10, txt=f"Final Total: ₹{totals['final_total']}", ln=1)

    pdf.output(save_path)


def export_bill_csv(order_id, items, totals, filename=None):
    if filename is None:
        filename = f"bill_order_{order_id}.csv"

    with open(filename, mode="w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Item", "Quantity", "Price", "Total"])
        for item in items:
            writer.writerow([
                item['name'],
                item['quantity'],
                f"{item['price']:.2f}",
                f"{item['quantity'] * item['price']:.2f}"
            ])
        writer.writerow([])
        writer.writerow(["Subtotal", f"{totals['subtotal']:.2f}"])
        writer.writerow(["Discount", f"{totals['discount']:.2f}"])
        writer.writerow(["Tax", f"{totals['tax']:.2f}"])
        writer.writerow(["Final Total", f"{totals['final_total']:.2f}"])
    return filename


def export_bill_json(order_id, items, totals, filename=None):
    if filename is None:
        filename = f"bill_order_{order_id}.json"

    data = {
        "order_id": order_id,
        "date": datetime.now().strftime('%Y-%m-%d %H:%M'),
        "items": items,
        "totals": totals
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    return filename


