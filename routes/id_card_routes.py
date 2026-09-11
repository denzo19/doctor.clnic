import base64
import mimetypes
import os
import uuid

from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from auth import login_required, permission_required
from i18n import translate


ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"}


def register_id_card_routes(app):
    def flash_t(message, category="success"):
        flash(translate(message, session.get("language", "en")), category)

    def allowed_image(filename):
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

    def save_uploaded_image(image_file):
        upload_dir = os.path.join(app.root_path, "static", "uploads", "id_cards")
        os.makedirs(upload_dir, exist_ok=True)

        original_name = secure_filename(image_file.filename or "")
        if "." not in original_name:
            raise ValueError("Upload a valid image file with an extension.")

        extension = original_name.rsplit(".", 1)[1].lower()
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError("Upload a valid image file.")

        stored_name = f"{uuid.uuid4().hex}.{extension}"
        absolute_path = os.path.join(upload_dir, stored_name)
        image_file.save(absolute_path)

        return absolute_path, f"uploads/id_cards/{stored_name}"

    def image_data_url(image_path):
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        with open(image_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def extract_visible_text_with_openai(image_path):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "", "OPENAI_API_KEY is not configured."

        try:
            from openai import OpenAI
            import httpx
        except Exception:
            return "", "OpenAI Python SDK is not installed."

        prompt = (
            "Read all visible text in this image, including handwritten text and printed text. "
            "Preserve the original language, especially Arabic text. Do not translate. "
            "Preserve line breaks as much as possible. "
            "Return only the extracted text, with no explanation and no markdown."
        )

        try:
            client = OpenAI(
                api_key=api_key,
                http_client=httpx.Client(trust_env=False, timeout=60.0)
            )
            response = client.responses.create(
                model=os.getenv("OPENAI_ID_CARD_MODEL", "gpt-4o-mini"),
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {"type": "input_image", "image_url": image_data_url(image_path)},
                        ],
                    }
                ],
            )
            return (getattr(response, "output_text", "") or "").strip(), ""
        except Exception as error:
            return "", f"OpenAI image text extraction failed: {error}"

    @app.route("/clinic/id_card", methods=["GET", "POST"])
    @login_required
    @permission_required("id_card")
    def id_card():
        extracted_text = ""
        image_path = ""

        if request.method == "POST":
            image_file = request.files.get("id_card_image")

            if not image_file or not image_file.filename:
                flash_t("Choose an image first.", "error")
                return redirect(url_for("id_card"))

            if not allowed_image(image_file.filename):
                flash_t("Upload a valid image file.", "error")
                return redirect(url_for("id_card"))

            try:
                absolute_path, image_path = save_uploaded_image(image_file)
            except ValueError as error:
                flash_t(str(error), "error")
                return redirect(url_for("id_card"))

            extracted_text, warning = extract_visible_text_with_openai(absolute_path)

            if warning:
                flash_t(warning, "error")
            elif extracted_text:
                flash_t("Image text extracted by OpenAI.", "success")
            else:
                flash_t("No readable text was extracted from this image.", "error")

        return render_template(
            "id_card.html",
            extracted_text=extracted_text,
            image_path=image_path
        )
