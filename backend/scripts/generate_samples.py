"""Generate the evaluation dataset into ``sample_dataset/``.

    5 resumes (txt/pdf/docx) 2 invoices, 2 contracts, 2 certificates,
    1 corrupted file, 2 scanned PDFs (image-only), 2 duplicate resumes,
    plus expected_outputs.json for extraction-quality measurement.

Usage: python scripts/generate_samples.py
"""
from __future__ import annotations

import json
from pathlib import Path

from docx import Document as DocxDocument
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parents[2] / "sample_dataset"
OUT.mkdir(parents=True, exist_ok=True)

RESUMES = [
    {
        "file": "john_doe_resume",
        "text": """John Doe
john.doe@gmail.com
+91-9876543210
Varanasi, India

Skills:
Python, SQL, AWS, Docker, Machine Learning

Experience:
1.5 years

Education:
B.Tech Computer Science
""",
        "expected": {
            "name": "John Doe", "email": "john.doe@gmail.com",
            "phone": "+91-9876543210", "location": "Varanasi, India",
            "skills": ["Python", "SQL", "AWS", "Docker", "Machine Learning"],
            "years": 1.5, "degree": "B.Tech", "field": "Computer Science",
        },
    },
    {
        "file": "priya_sharma_resume",
        "text": """Priya Sharma
priya.sharma@outlook.com
+91 9812345678
Bengaluru, India

Professional Summary:
Full-stack engineer building web products end to end.

Skills:
JavaScript, TypeScript, React.js, Node JS, MongoDB, Docker, Kubernetes, AWS

Experience:
4 years of experience

Education:
B.Tech Information Technology, 2020

Certifications:
AWS Certified Developer - Associate
""",
        "expected": {
            "name": "Priya Sharma", "email": "priya.sharma@outlook.com",
            "phone": "+91 9812345678", "location": "Bengaluru, India",
            "skills": ["JavaScript", "TypeScript", "React", "Node.js",
                       "MongoDB", "Docker", "Kubernetes", "AWS"],
            "years": 4.0, "degree": "B.Tech", "field": "Information Technology",
        },
    },
    {
        "file": "michael_chen_resume",
        "text": """Michael Chen
m.chen@example.com
+1-415-555-0132
San Francisco, USA

Skills:
Java, Spring Boot, Postgre SQL, Redis, Kafka, Microservices, CI/CD

Experience:
Senior Backend Engineer at FinEdge (2021-2024)
6 years experience

Education:
M.Sc Computer Science, Stanford University, 2019

Languages:
English, Mandarin
""",
        "expected": {
            "name": "Michael Chen", "email": "m.chen@example.com",
            "phone": "+1-415-555-0132", "location": "San Francisco, USA",
            "skills": ["Java", "Spring Boot", "PostgreSQL", "Redis",
                       "Kafka", "Microservices", "CI/CD"],
            "years": 6.0, "degree": "M.Sc", "field": "Computer Science",
        },
    },
    {
        "file": "aisha_khan_resume",
        "text": """Aisha Khan
aisha.khan@gmail.com
+91-9988776655
Hyderabad, India

Skills:
Python, TensorFlow, PyTorch, NLP, scikit-learn, Pandas, NumPy, MLOps

Experience:
Machine Learning Engineer, 3 years

Education:
M.Tech Artificial Intelligence, IIIT Hyderabad, 2022

Certifications:
Deep Learning Specialization - Coursera
""",
        "expected": {
            "name": "Aisha Khan", "email": "aisha.khan@gmail.com",
            "phone": "+91-9988776655", "location": "Hyderabad, India",
            "skills": ["Python", "TensorFlow", "PyTorch", "NLP",
                       "scikit-learn", "Pandas", "NumPy", "MLOps"],
            "years": 3.0, "degree": "M.Tech", "field": "Artificial Intelligence",
        },
    },
    {
        "file": "rahul_verma_resume",
        "text": """Rahul Verma
rahul.verma@yahoo.in
+91 8877665544
Delhi, India

Skills:
Go, Kubernetes, Terraform, AWS, GCP, Linux, Bash, Prometheus monitoring

Experience:
DevOps Engineer at CloudNine, 5 years

Education:
B.E. Electronics, 2019
""",
        "expected": {
            "name": "Rahul Verma", "email": "rahul.verma@yahoo.in",
            "phone": "+91 8877665544", "location": "Delhi, India",
            "skills": ["Go", "Kubernetes", "Terraform", "AWS", "GCP",
                       "Linux", "Bash"],
            "years": 5.0, "degree": "B.E.", "field": "Electronics",
        },
    },
]

DUPLICATES = [
    (
        "john_doe_resume_copy.txt",
        RESUMES[0]["text"].replace("John Doe", "JOHN DOE"),
    ),
    (
        "priya_sharma_resume_v2.txt",
        RESUMES[1]["text"] + "\nLooking for a senior full-stack role.\n",
    ),
]

INVOICES = {
    "invoice_acme.txt": """INVOICE
Invoice Number: INV-2026-1042
Bill To: Acme Corporation, 5th Avenue, New York
Subtotal: 2400.00
Tax: 432.00
Total Due: 2832.00
Payment Terms: Net 30
Amount Due: 2832.00
""",
    "invoice_globex.txt": """INVOICE
Invoice Number: 88-B
Bill To: Globex Inc
Subtotal: 999.99
Tax: 99.99
Total Due: 1099.98
Payment Terms: Due on receipt
Amount Due: 1099.98
""",
}

CONTRACTS = {
    "contract_services.txt": """SERVICES AGREEMENT
This agreement is entered into by and between Alpha Ltd and Beta LLP (the "parties").
WHEREAS, the parties wish to define the terms and conditions of service;
NOW THEREFORE the parties agree to indemnify each other.
Governing Law: India. Termination clause applies after 30 days notice.
""",
    "contract_nda.txt": """NON-DISCLOSURE AGREEMENT
This agreement is made between the disclosing party and the receiving party.
The parties hereby agree to the following terms and conditions.
Governing law: United States. Each party shall indemnify the other
against unauthorized disclosure claims.
""",
}

CERTIFICATES = {
    "certificate_completion.txt": """CERTIFICATE OF COMPLETION
This is to certify that Ravi Patel has completed the
Advanced Kubernetes Administration program.
Awarded to Ravi Patel. Issued on 2026-03-14.
""",
    "certificate_award.txt": """CERTIFICATE
This is to certify that Meera Iyer is awarded the
Employee Excellence Award for 2026.
Issued on 2026-06-01. Of completion of the annual review cycle.
""",
}


def main() -> None:
    expected: dict[str, dict] = {}

    for resume in RESUMES:
        (OUT / f"{resume['file']}.txt").write_text(resume["text"])
        expected[f"{resume['file']}.txt"] = resume["expected"]

    # same resume content across formats (pdf + docx)
    _write_pdf(OUT / "john_doe_resume.pdf", RESUMES[0]["text"])
    _write_docx(OUT / "priya_sharma_resume.docx", RESUMES[1]["text"])

    for name, text in DUPLICATES:
        (OUT / name).write_text(text)
    for name, text in (INVOICES | CONTRACTS | CERTIFICATES).items():
        (OUT / name).write_text(text)

    # corrupted file: truncated garbage claiming to be a PDF
    (OUT / "corrupted_file.pdf").write_bytes(b"%PDF-1.7 garbage\x00\x01\x02 broken")

    # scanned PDFs: image-only pages (no text layer) to exercise the OCR path
    for i, label in enumerate(("scanned_resume", "scanned_contract"), 1):
        _write_scanned_pdf(OUT / f"{label}.pdf", f"SCANNED {label.upper()} PAGE {i}")

    (OUT / "expected_outputs.json").write_text(json.dumps(expected, indent=2))
    print(f"Wrote {len(list(OUT.iterdir()))} files to {OUT}")


def _write_pdf(path: Path, text: str) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)
    y = 750
    for line in text.splitlines():
        c.drawString(72, y, line)
        y -= 16
    c.save()


def _write_docx(path: Path, text: str) -> None:
    doc = DocxDocument()
    for line in text.splitlines():
        doc.add_paragraph(line)
    doc.save(path)


def _write_scanned_pdf(path: Path, label: str) -> None:
    from PIL import Image, ImageDraw

    img_path = path.with_suffix(".png.png")
    img = Image.new("RGB", (700, 200), "white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 80), label, fill="black")
    img.save(img_path)
    c = canvas.Canvas(str(path), pagesize=(720, 220))
    c.drawImage(str(img_path), 10, 10, width=700, height=200)
    c.save()
    img_path.unlink()


if __name__ == "__main__":
    main()
