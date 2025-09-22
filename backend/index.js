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
    // Determine filename based on existing files
    const files = fs.readdirSync(uploadDir).filter(f => f.endsWith('.pdf'));
    let newFilename = '';
    if (!files.includes('pdf_a.pdf')) {
      newFilename = 'pdf_a.pdf';
    } else if (!files.includes('pdf_b.pdf')) {
      newFilename = 'pdf_b.pdf';
    } else {
      return res.status(400).json({ error: "Only two PDFs allowed: pdf_a and pdf_b." });
    }

    // Move uploaded file to new name
    const oldPath = req.file.path;
    const newPath = path.join(uploadDir, newFilename);
    fs.renameSync(oldPath, newPath);

    // Call AI processing function
    const aiResult = await processPDF(newPath);

    res.json({
      message: "File uploaded successfully",
      file: {
        originalName: req.file.originalname,
        filename: newFilename,
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