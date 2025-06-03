import io
import os
import json
import zipfile
from flask import Flask, request, render_template, send_file, abort, send_from_directory

app = Flask(__name__)

# Read template paths from environment variables (with sensible defaults)
XML_TEMPLATE_PATH = os.environ.get("XML_TEMPLATE_PATH", "xml_template.xml")
META_BLOCK_PATH = os.environ.get("META_BLOCK_PATH", "meta_block.xml")


def markRight(quiz_content: str, qnum: int, optionNo: int) -> str:
    """
    Given the XML text containing placeholders like {{Option_11}}, {{Option_12}} …,
    replace each Option_{qnum}{i} with "true"/"false" based on which index matches optionNo.
    optionNo is zero‐based (0 → first answer, 1 → second, etc.).
    """
    for i in range(1, 5):  # answers 1..4
        correct_value = "true" if (i - 1) == optionNo else "false"
        placeholder = f"{{{{Option_{qnum}{i}}}}}"
        quiz_content = quiz_content.replace(placeholder, correct_value)
    return quiz_content


@app.route("/", methods=["GET"])
def upload_page():
    return render_template("upload.html")

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')

@app.route("/generate_xmls", methods=["POST"])
def generate_xmls():
    # 1) Ensure both file and base_name are provided:
    if "quiz_json" not in request.files:
        return abort(400, "No JSON file part")
    quiz_file = request.files["quiz_json"]
    base_name = request.form.get("base_name", "").strip()
    if not base_name:
        return abort(400, "Base filename is required")

    # 2) Read the uploaded JSON into memory:
    try:
        data = json.load(quiz_file)
    except Exception as e:
        return abort(400, f"Invalid JSON: {e}")

    # 3) Load the XML template and meta block dynamically:
    try:
        with open(XML_TEMPLATE_PATH, "r", encoding="utf-8") as tmpl:
            xml_template = tmpl.read()
        with open(META_BLOCK_PATH, "r", encoding="utf-8") as mb:
            meta_block_template = mb.read()
    except FileNotFoundError as e:
        return abort(500, f"Template files not found: {e}")

    # 4) Create an in‐memory ZIP:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Assume data["quizzes"] is a list of quiz dicts:
        for idx, quiz in enumerate(data.get("quizzes", []), start=1):
            # Start from a fresh copy of the template:
            quiz_content = xml_template

            # Replace TITLE:
            quiz_content = quiz_content.replace("{{TITLE}}", quiz["TITLE"])

            # For each question (1..N), replace placeholders:
            for qnum, q in enumerate(quiz["QUESTIONS"], start=1):
                # QUESTION text:
                quiz_content = quiz_content.replace(
                    f"{{{{QUESTION_{qnum}}}}}", q["QUESTION"]
                )

                # ANSWER placeholders are ANSWER_{qnum}A, B, C, D
                for anum, answer_text in enumerate(q["ANSWERS"], start=1):
                    placeholder = f"{{{{ANSWER_{qnum}{chr(64 + anum)}}}}}"
                    quiz_content = quiz_content.replace(placeholder, answer_text)

                # Mark the correct option (zero‐based index in q["CORRECT"]):
                quiz_content = markRight(quiz_content, qnum, q["CORRECT"])

            # Now append the meta_block, substituting {{ID}}:
            mb_filled = meta_block_template.replace("{{ID}}", str(quiz["id"]))

            # Final XML text for this single quiz:
            full_xml = quiz_content + mb_filled

            # Name the file: e.g. base_name_1.xml, base_name_2.xml, etc.
            filename = f"{base_name}_{idx}.xml"
            zipf.writestr(filename, full_xml)

    zip_buffer.seek(0)

    # 5) Send ZIP back as a downloadable file:
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{base_name}_xmls.zip",
    )


if __name__ == "__main__":
    # Run on http://127.0.0.1:5000/
    # You can override DEBUG and host/port via environment variables if needed.
    debug_mode = os.environ.get("FLASK_DEBUG", "True").lower() == "true"
    app.run(debug=debug_mode, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
