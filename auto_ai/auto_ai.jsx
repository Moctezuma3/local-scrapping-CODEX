function readFormatsFromFile(filePath) {
    var formats = [];
    var inputFile = File(filePath);

    if (inputFile.exists) {
        inputFile.open('r');
        while (!inputFile.eof) {
            var line = inputFile.readln().trim();
            if (line) {
                formats.push(line.toLowerCase());  
            }
        }
        inputFile.close();
    } else {
        alert("Fichier input.txt introuvable.");
    }

    return formats;
}

function readPathsFromFile(filePath) {
    var paths = {};
    var inputFile = File(filePath);

    if (inputFile.exists) {
        inputFile.open('r');
        while (!inputFile.eof) {
            var line = inputFile.readln().trim();
            if (line) {
                var keyValue = line.split('=');
                if (keyValue.length === 2) {
                    paths[keyValue[0].trim()] = keyValue[1].trim();
                }
            }
        }
        inputFile.close();
    } else {
        alert("Fichier paths.txt introuvable.");
    }

    return paths;
}

var paths = readPathsFromFile("/chemin/vers/paths.txt");
var inputFolderPath = paths['input_folder'];
var outputFolderPath = paths['output_folder'];

var formatsFilePath = inputFolderPath + "/input.txt";

var outputFolder = new Folder(outputFolderPath);
if (!outputFolder.exists) {
    outputFolder.create();
}

var formats = readFormatsFromFile(formatsFilePath);

if (formats.length > 0) {
    var inputFolder = new Folder(inputFolderPath);
    var aiFiles = inputFolder.getFiles("*.ai");  

    if (aiFiles.length > 0) {
        for (var j = 0; j < aiFiles.length; j++) {
            var aiFile = aiFiles[j];
            var doc = app.open(aiFile);  
            
            for (var i = 0; i < formats.length; i++) {
                var format = formats[i];
                
                if (format === 'pdf') {
                    var pdfOptions = new PDFSaveOptions();
                    pdfOptions.preserveEditability = true;
                    var pdfFile = new File(outputFolderPath + "/" + aiFile.name.replace(".ai", ".pdf"));
                    doc.saveAs(pdfFile, pdfOptions);
                    alert("Exporté en PDF : " + pdfFile);
                } else if (format === 'jpeg') {
                    var jpegOptions = new ExportOptionsJPEG();
                    jpegOptions.qualitySetting = 100;
                    var jpegFile = new File(outputFolderPath + "/" + aiFile.name.replace(".ai", ".jpeg"));
                    doc.exportFile(jpegFile, ExportType.JPEG, jpegOptions);
                    alert("Exporté en JPEG : " + jpegFile);
                } else if (format === 'png') {
                    var pngOptions = new ExportOptionsPNG24();
                    pngOptions.antiAliasing = true;
                    pngOptions.transparency = true;
                    var pngFile = new File(outputFolderPath + "/" + aiFile.name.replace(".ai", ".png"));
                    doc.exportFile(pngFile, ExportType.PNG24, pngOptions);
                    alert("Exporté en PNG : " + pngFile);
                } else if (format === 'svg') {
                    var svgOptions = new ExportOptionsSVG();
                    var svgFile = new File(outputFolderPath + "/" + aiFile.name.replace(".ai", ".svg"));
                    doc.exportFile(svgFile, ExportType.SVG, svgOptions);
                    alert("Exporté en SVG : " + svgFile);
                } else {
                    alert("Format non supporté : " + format);
                }
            }

            doc.close(SaveOptions.DONOTSAVECHANGES);
        }
    } else {
        alert("Aucun fichier .ai trouvé dans le dossier input.");
    }
} else {
    alert("Aucun format spécifié dans input.txt.");
}
