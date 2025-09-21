import React, { useState, useRef, useEffect } from "react";
import { gsap } from "gsap";
import GridDistortion from "./GridDistortion";
import BlurText from "./BlurText";
import "./App.css";

function App() {
  const [pdfs, setPdfs] = useState([]);
  const pdfRefs = useRef([]);
  const headingRef = useRef(null);
  const dropRef = useRef(null);

  // GSAP animations
  useEffect(() => {
    gsap.fromTo(
      headingRef.current,
      { opacity: 0, y: -60 },
      { opacity: 1, y: 0, duration: 1.2, ease: "power3.out" }
    );

    pdfRefs.current.forEach((el, i) => {
      if (el) {
        gsap.fromTo(
          el,
          { opacity: 0, y: 50, scale: 0.95 },
          {
            opacity: 1,
            y: 0,
            scale: 1,
            duration: 0.6,
            delay: i * 0.15,
            ease: "power3.out",
          }
        );
      }
    });
  }, [pdfs]);

  // File upload handler
  const handleFiles = (files) => {
    const pdfFiles = Array.from(files).filter(
      (file) => file.type === "application/pdf"
    );
    setPdfs((prev) => [...prev, ...pdfFiles]);
  };

  const handleFileChange = (e) => handleFiles(e.target.files);

  // Drag & Drop
  const handleDragOver = (e) => e.preventDefault();
  const handleDrop = (e) => {
    e.preventDefault();
    handleFiles(e.dataTransfer.files);
  };

  // Hover animation for PDF cards
  const handleMouseEnter = (index) => {
    gsap.to(pdfRefs.current[index], {
      scale: 1.05,
      y: -5,
      duration: 0.3,
      ease: "power3.out",
    });
  };
  const handleMouseLeave = (index) => {
    gsap.to(pdfRefs.current[index], {
      scale: 1,
      y: 0,
      duration: 0.3,
      ease: "power3.out",
    });
  };

  return (
    <div className="App">
      <GridDistortion
        imageSrc="/gradient-3d-fluid-background.jpg"
        grid={10}
        mouse={0.1}
        strength={0.15}
        relaxation={0.9}
        className="custom-class"
      />

      <div className="content">
        <BlurText
          text="✨ Drag & Drop Your PDFs Here"
          delay={300}
          animateBy="words"
          direction="top"
          className="text-4xl mb-8"
          onAnimationComplete={() => console.log("Heading animation done!")}
        />

        {/* Drag & Drop / Click */}
        <div
          className="drop-zone"
          ref={dropRef}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onClick={() => document.getElementById("fileInput").click()}
        >
          <p>Drag & Drop PDFs here or Click to Upload</p>
          <input
            id="fileInput"
            type="file"
            accept="application/pdf"
            multiple
            onChange={handleFileChange}
            style={{ display: "none" }}
          />
        </div>

        <div className="pdf-list">
          {pdfs.map((pdf, index) => (
            <div
              key={index}
              ref={(el) => (pdfRefs.current[index] = el)}
              className="pdf-item"
              onMouseEnter={() => handleMouseEnter(index)}
              onMouseLeave={() => handleMouseLeave(index)}
            >
              {pdf.name}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default App;
