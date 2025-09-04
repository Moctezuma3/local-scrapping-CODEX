import subprocess
import os
import platform

output_folder = os.path.join('..', 'output')  
input_folder = os.path.join('..', 'input') 

with open('paths.txt', 'w') as f:
    f.write(f"input_folder={input_folder}\n")
    f.write(f"output_folder={output_folder}\n") 


print("Chemins écrits dans paths.txt")

def run_illustrator_script(illustrator_script_path):
    print(f"Lancement du script Illustrator : {illustrator_script_path}")
    
    if platform.system() == 'Darwin':  
        command = f'osascript -e \'tell application "Adobe Illustrator" to do javascript "{illustrator_script_path}"\''
    elif platform.system() == 'Windows':  
        command = f'"C:\\Program Files\\Adobe\\Adobe Illustrator 2021\\Support Files\\Contents\\Windows\\Illustrator.exe" -run "{illustrator_script_path}"'
    else:
        raise OSError("Système d'exploitation non supporté")

    try:
        subprocess.run(command, shell=True, check=True)
        print(f"Le script {illustrator_script_path} a été exécuté avec succès.")
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de l'exécution du script : {e}")

script_path = os.path.join('..', 'export_script.jsx')  

print(f"Chemin du script JSX : {script_path}")
run_illustrator_script(script_path)
