// Quick script to create placeholder icon files for Tauri
const fs = require('fs');
const path = require('path');

const iconsDir = path.join(__dirname, 'src-tauri', 'icons');

// Create icons directory if it doesn't exist
if (!fs.existsSync(iconsDir)) {
  fs.mkdirSync(iconsDir, { recursive: true });
}

// Create empty placeholder files - Tauri will fail gracefully if these are wrong,
// but at least the build will proceed
const files = [
  '32x32.png',
  '128x128.png',
  '128x128@2x.png',
  'icon.icns',
  'icon.ico',
  'icon.png',
  'Square30x30Logo.png',
  'Square44x44Logo.png',
  'Square71x71Logo.png',
  'Square89x89Logo.png',
  'Square107x107Logo.png',
  'Square142x142Logo.png',
  'Square150x150Logo.png',
  'Square284x284Logo.png',
  'Square310x310Logo.png',
  'StoreLogo.png'
];

files.forEach(file => {
  const filePath = path.join(iconsDir, file);
  if (!fs.existsSync(filePath)) {
    // Create an empty file
    fs.writeFileSync(filePath, '');
    console.log(`Created placeholder: ${file}`);
  }
});

console.log('\nPlaceholder icons created!');
console.log('\nIMPORTANT: These are empty placeholders.');
console.log('To create proper icons, run:');
console.log('  npm run tauri icon path/to/your/icon.png');
console.log('\nOr download icons from: https://icon-icons.com/');
