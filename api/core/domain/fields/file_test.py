from core.domain.fields.file import File


class TestFile:
    def test_validate_url(self):
        img = File(url="https://bla.com/file.png")
        assert img.to_url() == "https://bla.com/file.png"
        assert img.content_type == "image/png"

    def test_validate_data(self):
        img = File(data="iVBORw0KGgoAAAANSUhEUgAAAAUA", content_type="image/png")
        assert img.to_url() == "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"
        assert img.content_type == "image/png"

    def test_validate_data_url(self):
        img = File(url="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA")
        assert img.to_url() == "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"
        assert img.content_type == "image/png"
        assert img.data == "iVBORw0KGgoAAAANSUhEUgAAAAUA"

    def test_validate_data_content_type(self):
        img = File(
            url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExYXQxbTFybW0wZWs2M3RkY3gzNXZlbXp4aHhkcTl4ZzltN2V6Y21lcCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/rkFQ8LrdXcP5e/giphy.webp",
        )
        assert img.content_type == "image/webp"

    def test_validate_data_content_type_none(self):
        img = File(url="https://bla.com/file")
        assert img.content_type is None
