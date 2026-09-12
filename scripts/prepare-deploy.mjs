import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "..");

const staticSrcDir = path.join(rootDir, "python_orchestrator", "src", "webcmd", "web", "static");
const targetDirs = [
  path.join(rootDir, "dist", "public"),
  path.join(rootDir, "dist", "public", "static"),
  path.join(rootDir, "dist"),
  path.join(rootDir, "dist", "static"),
  path.join(rootDir, "public"),
  path.join(rootDir, "public", "static"),
  rootDir,
];

console.log("Preparing WebCMD deployment assets...");
console.log(`Source directory: ${staticSrcDir}`);

if (!fs.existsSync(staticSrcDir)) {
  console.error(`Error: Static source directory does not exist: ${staticSrcDir}`);
  process.exit(1);
}

const files = fs.readdirSync(staticSrcDir);

for (const targetDir of targetDirs) {
  if (!fs.existsSync(targetDir)) {
    fs.mkdirSync(targetDir, { recursive: true });
  }

  for (const file of files) {
    const srcFile = path.join(staticSrcDir, file);
    const destFile = path.join(targetDir, file);
    const stat = fs.statSync(srcFile);
    if (stat.isFile()) {
      fs.copyFileSync(srcFile, destFile);
      console.log(`  [OK] Copied ${file} -> ${path.relative(rootDir, destFile)}`);
    }
  }
}

console.log("WebCMD deployment assets prepared successfully across target directories.");
