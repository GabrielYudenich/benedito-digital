import subprocess
import os

class Extractor:
    def __init__(self, project_config: dict):
        self.input_path = project_config['originals']
        self.output_path = project_config['frames']

    def extract(self, video_index: int):

        name_file = os.path.splitext(os.path.basename(self.input_path[video_index]))[0].replace(' ', '_')

        output_pattern = os.path.join(self.output_path, f"{name_file}_frame_%06d.jpg")
        cmd = [
            "ffmpeg",
            "-i", self.input_path[video_index],
            "-q:v", "2",
            "-vsync", "0",
            output_pattern
        ]

        result = subprocess.run(cmd, check=True)

        if result.returncode == 0:
            print(f'Extraiu frames do video {video_index}')
            return True
        else:
            print(f'Erro ao extrair frames do video {video_index}')
            return False
