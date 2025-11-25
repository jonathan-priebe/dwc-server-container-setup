from flask import Flask, send_from_directory, jsonify, send_file
import os, io, zipfile

app = Flask(__name__)
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/work/DLC")

@app.route("/")
def index():
    # Simple HTML page with Download and Browser Button
    return """
    <html>
      <body>
        <h1>DLC Download</h1>
        <a href="/download-zip">
          <button>Download myg ZIP</button>
        </a>
        <a href="/browse">
          <button>Browse</button>
        </a>
      </body>
    </html>
    """

@app.route("/download-zip")
def download_zip():
    # Create ZIP in memory
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(OUTPUT_DIR):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, OUTPUT_DIR)
                zf.write(abs_path, rel_path)
    mem_zip.seek(0)
    return send_file(mem_zip,
                     mimetype="application/zip",
                     as_attachment=True,
                     download_name="dlc.zip")

@app.route("/browse")
def browse():
    # Simple HTML-Page with all Data in OUTPUT_DIR
    html = "<h1>Browse DLC</h1><ul>"
    for root, dirs, files in os.walk(OUTPUT_DIR):
        rel_root = os.path.relpath(root, OUTPUT_DIR)
        for file in files:
            rel_path = os.path.join(rel_root, file)
            # Link to Download of Data
            html += f'<li><a href="/dlc/{rel_path}">{rel_path}</a></li>'
    html += "</ul>"
    return html

@app.route("/dlc/<path:filename>")
def download(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)