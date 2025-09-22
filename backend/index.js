const express = require("express");
const cors = require("cors");
const multer = require("multer");
const path = require("path");
const fs = require("fs");
const { processPDF } = require("./ai");

const app = express();
const PORT = 5000;

// Enable CORS
app.use(cors());

// Ensure uploads folder exists
const uploadDir = path.join(__dirname, "uploads");
if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir);

// Multer config
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, uploadDir),
  filename: (req, file, cb) =>
    cb(null, Date.now() + path.extname(file.originalname)),
});
const upload = multer({ storage });

// Upload endpoint
app.post("/upload", upload.single("file"), async (req, res) => {
  try {
    const filePath = req.file.path;

    // Call AI processing function
    const aiResult = await processPDF(filePath);

    res.json({
      message: "File uploaded successfully",
      file: {
        originalName: req.file.originalname,
        filename: req.file.filename,
      },
      aiResult,
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Upload failed" });
  }
});

// List uploaded files
app.get("/files", (req, res) => {
  fs.readdir(uploadDir, (err, files) => {
    if (err) return res.status(500).json({ error: "Could not read files" });
    res.json(files);
  });
});

// Start server
app.listen(PORT, () => console.log(`✅ Backend running at http://localhost:${PORT}`));