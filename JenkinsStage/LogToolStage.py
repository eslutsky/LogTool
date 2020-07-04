#!/usr/bin/python2

# Copyright 2018 Arkady Shtempler.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import shutil
from Common import *
from Params import *
import unittest
import warnings
import threading
import sys
import time
from urllib2 import urlparse
from urlparse import urljoin

spec_print([artifact_url,user_start_time])

# Parameters #
errors_on_execution = {}
competed_nodes={}
workers_output={}

### Check given by user user_start_time ###
if check_time(user_start_time)!=True:
    print_in_color('FATAL ERROR - provided "start_time" value: "'+user_start_time+'" in Params.py is incorrect!!!')
    sys.exit(1)

### Create Result Folders ###
if result_dir in os.listdir('.'):
    shutil.rmtree(result_dir)
os.mkdir(result_dir)

class LogTool(unittest.TestCase):
    @staticmethod
    def raise_warning(msg):
        warnings.warn(message=msg, category=Warning)

    def test_1_download_jenkins_job(selfself):
        mode_start_time=time.time()
        # Create destination directory
        destination_dir = 'Jenkins_Job_Files'
        destination_dir = os.path.join(os.path.dirname(os.path.abspath('.')), destination_dir)
        if os.path.exists(destination_dir):
            shutil.rmtree(destination_dir)
        os.mkdir(destination_dir)
        #Import BeautifulSoup
        try:
            from BeautifulSoup import BeautifulSoup
        except Exception as e:
            print_in_color(str(e), 'red')
            print_in_color('Execute "pip install beautifulsoup" to install it!', 'yellow')
            exit('Install beautifulsoup and rerun!')
        # Download logs
        response = urllib2.urlopen(artifact_url)
        html = response.read()
        parsed_url = urlparse.urlparse(artifact_url)
        base_url = parsed_url.scheme + '://' + parsed_url.netloc
        soup = BeautifulSoup(html)
        tar_gz_files = []
        ir_logs_urls = []
        tempest_log_url = None
        for link in soup.findAll('a'):
            if 'tempest-results' in link:
                tempest_results_url = urljoin(artifact_url, link.get('href'))
                tempest_response = urllib2.urlopen(tempest_results_url)
                html = tempest_response.read()
                soup = BeautifulSoup(html)
                for link in soup.findAll('a'):
                    if str(link.get('href')).endswith('.html'):
                        tempest_html = link.get('href')
                        tempest_log_url = urljoin(artifact_url, 'tempest-results') + '/' + tempest_html
                        break
            if str(link.get('href')).endswith('.tar.gz'):
                tar_gz_files.append(link)
                tar_link = urlparse.urljoin(artifact_url, link.get('href'))
                os.system('wget -P ' + destination_dir + ' ' + tar_link)
            if str(link.get('href')).endswith('.sh'):
                sh_page_link = urlparse.urljoin(artifact_url, link.get('href'))
                response = urllib2.urlopen(sh_page_link)
                html = response.read()
                soup = BeautifulSoup(html)
                for link in soup.findAll('a'):
                    if str(link.get('href')).endswith('.log'):
                        ir_logs_urls.append(sh_page_link + '/' + link.get('href'))
        console_log_url=artifact_url.strip().replace('artifact','consoleFull').strip('/')
        os.system('wget -P ' + destination_dir + ' ' + console_log_url)
        shutil.move(os.path.join(destination_dir, 'consoleFull'),os.path.join(destination_dir,'consoleFull.log'))
        # Download Infared Logs .sh, files in .sh directory on Jenkins
        if len(ir_logs_urls)!=0:
            for url in ir_logs_urls:
                os.system('wget -P ' + destination_dir + ' ' + url)
        # Download tempest log (html #)
        if tempest_log_url!=None:
            os.system('wget -P ' + destination_dir + ' ' + tempest_log_url)
            shutil.move(os.path.join(destination_dir, tempest_html),os.path.join(destination_dir,tempest_html.replace('.html','.log')))
        # Unzip all downloaded .tar.gz files
        for fil in os.listdir(os.path.abspath(destination_dir)):
            if fil.endswith('.tar.gz'):
                cmd = 'tar -zxvf ' + os.path.join(os.path.abspath(destination_dir), fil) + ' -C ' + os.path.abspath(
                    destination_dir) + ' >/dev/null' + ';' + 'rm -rf ' + os.path.join(
                    os.path.abspath(destination_dir), fil)
                print_in_color('Unzipping ' + fil + '...', 'bold')
                os.system(cmd)
                os.system('rm -rf '+fil)
        # Run LogTool analyzing
        print_in_color('\nStart analyzing downloaded OSP logs locally', 'bold')
        result_dir = 'Jenkins_Job_' + grep_string.replace(' ', '')
        if os.path.exists(os.path.abspath(result_dir)):
            shutil.rmtree(os.path.abspath(result_dir))
        result_file = os.path.join(os.path.abspath(result_dir),
                                   'LogTool_Result_' + grep_string.replace(' ', '') + '.log')
        command = "python2 Extract_On_Node.py '" +user_start_time+ "' " + os.path.abspath(
            destination_dir) + " '" + grep_string + "'" + ' ' + result_file

        # shutil.copytree(destination_dir, os.path.abspath(result_dir))
        exec_command_line_command('cp -r ' + destination_dir + ' ' + os.path.abspath(result_dir))
        print_in_color('\n --> ' + command, 'bold')
        com_result = exec_command_line_command(command)
        # print (com_result['CommandOutput'])
        end_time = time.time()
        if 'SUCCESS!!!' in com_result['CommandOutput']:

            spec_print(com_result['CommandOutput'].splitlines()[-3:],'bold')

            spec_print(['Completed!!!',
                        "\nCheck LogTool results in 'Build Artifacts' directory: "+os.path.basename(result_dir),
                        '\nLogTool ResultFile is: '+os.path.basename(result_file),
                        'Analyzing time: ' + str(round(end_time - mode_start_time, 2)) + '[sec]'],
                        'blue')
        else:
            spec_print(['Completed!!!', 'Result Directory: ' + result_dir,
                        'Analyze logs execution time: ' + str(round(end_time - mode_start_time, 2)) + '[sec]'],
                       'red')

