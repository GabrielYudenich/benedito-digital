from datetime import datetime
import json
import os
import random
import shutil

from core.paths import default_projects_dir, resource_path

class ProjectManager:
    def __init__(self):
        self.project_path = str(default_projects_dir())
        with resource_path('config.json').open('r', encoding='utf-8') as file_handle:
            self.config = json.load(file_handle)

    def create_project(self, project_name, author='Anonymous'):
        if not project_name or project_name in {'.', '..'} or os.path.basename(project_name) != project_name:
            return False
        os.makedirs(self.project_path, exist_ok=True)
        project_path = os.path.join(self.project_path, project_name)
        if os.path.exists(os.path.join(project_path, 'metadata', 'project.json')):
            return False
        os.makedirs(project_path, exist_ok=True)

        os.makedirs(f'{project_path}/metadata', exist_ok=True)

        with open(os.path.join(project_path, 'metadata', 'project.json'), 'w') as f:
            json.dump({
                'id': random.randint(0, 1000000),
                'name': project_name,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'creator': author,
                'software': self.config['software'],
                'version': self.config['version'],
                'language': self.config['language'],
                'license': self.config['license'],
                'description': self.config['description'],
                'frames': [],
                'videos': [],
                'originals': []
            }, f)

        return True

    def list_projects_in_path(self):

        projects_list = []

        os.makedirs(self.project_path, exist_ok=True)
        folders = os.listdir(self.project_path)

        for folder in folders:

            try:
                project = json.load(open(f'{self.project_path}/{folder}/metadata/project.json'))
            except:
                continue

            json_data = {'project_name': project['name'], 'project_path': folder, 'created_at': project['created_at'], 'updated_at': project['updated_at'], 'creator': project['creator']}
            projects_list.append(json_data)

        return projects_list

    def __update_project_dict(self, project_name):
        metadata_path = os.path.join(self.project_path, project_name, 'metadata', 'project.json')
        project = json.load(open(metadata_path))

        project['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with open(metadata_path, 'w') as f:
            json.dump(project, f)

        return True

    def __update_project_videos(self, project_name):
        project_path = os.path.join(self.project_path, project_name)
        metadata_path = os.path.join(project_path, 'metadata', 'project.json')
        project = json.load(open(metadata_path))
        originals_path = os.path.join(project_path, 'media', 'originals')
        videos = os.listdir(originals_path) if os.path.isdir(originals_path) else []

        project['videos'] = videos

        with open(metadata_path, 'w') as f:
            json.dump(project, f)

        return True

    def __update_project_originals(self, project_name):
        project_path = os.path.join(self.project_path, project_name)
        metadata_path = os.path.join(project_path, 'metadata', 'project.json')
        project = json.load(open(metadata_path))
        originals_path = os.path.join(project_path, 'media', 'originals')
        videos = os.listdir(originals_path) if os.path.isdir(originals_path) else []

        project['originals'] = videos

        with open(metadata_path, 'w') as f:
            json.dump(project, f)

        return True

    def __add_video_to_project(self, input_path, project_name):
        originals_path = os.path.join(self.project_path, project_name, 'media', 'originals')
        os.makedirs(originals_path, exist_ok=True)
        try:
            shutil.copy2(input_path, originals_path)
        except OSError:
            return False

        return True
