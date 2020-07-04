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

def set_default_arg_by_index(index, default):
    try:
        value=sys.argv[index]
        return value.strip()
    except:
        return default


















usage = ['LogTool - extracts Overcloud Errors and provides statistics',
         '1) Set needed configuration in Params.py configuration file.',
         '2) python2 -m unittest LogTool_Plugin.LogTool.test_1_Export_Overcloud_Errors',
         '3) python2 -m unittest LogTool_Plugin.LogTool',
         '4) Start specific test: "python2 -m unittest LogTool_Plugin.LogTool.test_1_Export_Overcloud_Errors" to start this script']
if len(sys.argv)==1 or (sys.argv[1] in ['-h','--help']):
    spec_print(usage, 'yellow')
    sys.exit(1)



# Parameters #
errors_on_execution = {}
competed_nodes={}
workers_output={}


### Check given by user_start_time ###
if check_time(user_start_time)!=True:
    print_in_color('FATAL ERROR - provided "user_start_time" value: "'+user_start_time+'" in Params.py is incorrect!!!')
    sys.exit(1)

### Get all nodes ###
try:
    nodes=[]
    all_nodes = exec_command_line_command('source ' + source_rc_file_path + 'stackrc;openstack server list -f json')['JsonOutput']
    all_nodes = [{'Name': item['name'], 'ip': item['networks'].split('=')[-1]} for item in all_nodes]
    for node in all_nodes:
        if check_ping(node['ip']) is True:
            nodes.append(node)
        else:
            print_in_color('Warning - ' + str(node) + ' will be skipped, due to connectivity issue!!!', 'yellow')
except Exception, e:
    print str(e)
    print "It's OK for test_3_download_jenkins_job :-)"

### Create Result Folders ###
if result_dir in os.listdir('.'):
    shutil.rmtree(result_dir)
os.mkdir(result_dir)


class LogTool(unittest.TestCase):
    @staticmethod
    def raise_warning(msg):
        warnings.warn(message=msg, category=Warning)

    @staticmethod
    def run_on_node(node):
        print('-------------------------')
        print(node)
        print('--------------------------')
        print('\n' + '-' * 40 + 'Remote Overcloud Node -->', str(node) + '-' * 40)
        result_file = node['Name'].replace(' ', '') + '.log'
        s = SSH(node['ip'], user=overcloud_ssh_user, key_path=overcloud_ssh_key)
        s.ssh_connect_key()
        s.scp_upload('Extract_On_Node.py', overcloud_home_dir + 'Extract_On_Node.py')
        s.ssh_command('chmod 777 ' + overcloud_home_dir + 'Extract_On_Node.py')
        command = "sudo " + overcloud_home_dir + "Extract_On_Node.py '" + str(
            user_start_time) + "' " + overcloud_logs_dir + " '" + grep_string + "'" + ' ' + result_file + ' ' + save_raw_data+' None '+log_type
        print('Executed command on host --> ', command)
        com_result = s.ssh_command(command)
        print(com_result['Stdout'])  # Do not delete me!!!
        if 'SUCCESS!!!' in com_result['Stdout']:
            print_in_color(str(node) + ' --> OK', 'green')
            workers_output[str(node)]=com_result['Stdout'].splitlines()[-2]
            competed_nodes[node['Name']] = True
        else:
            print_in_color(str(node) + ' --> FAILED', 'yellow')
            self.raise_warning(str(node) + ' --> FAILED')
            errors_on_execution[node['Name']] = False
        s.scp_download(overcloud_home_dir + result_file, os.path.join(os.path.abspath(result_dir), result_file+'.gz'))
        # Clean all #
        files_to_delete = ['Extract_On_Node.py', result_file]
        for fil in files_to_delete:
            s.ssh_command('rm -rf ' + fil)
        s.ssh_close()

    """ Start LogTool and export Errors from Overcloud, execution on nodes is running in parallel"""
    def test_1_Export_Overcloud_Errors(self):
        print('\ntest_1_Export_Overcloud_Errors')
        mode_start_time = time.time()
        threads=[]
        for node in nodes:
            t=threading.Thread(target=self.run_on_node, args=(node,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        script_end_time = time.time()
        if len(errors_on_execution) == 0:
            spec_print(['Completed!!!', 'Result Directory: ' + result_dir,
                        'Execution Time: ' + str(script_end_time - mode_start_time) + '[sec]'], 'green')
        else:
            if len(errors_on_execution)==len(nodes):
                spec_print(['Execution has failed for all nodes :-( ',
                           'Execution Time: ' + str(script_end_time - mode_start_time) + '[sec]'],'red')
            else:
                spec_print(['Completed with failures!!!', 'Result Directory: ' + result_dir,
                            'Execution Time: ' + str(script_end_time - mode_start_time) + '[sec]',
                            'Failed nodes:'] + [k for k in list(errors_on_execution.keys())], 'yellow')
        if len(competed_nodes)==0:
            self.raise_warning('LogTool execution has failed to be executed on all Overcloud nodes :-(')

    """ Start LogTool and export Errors from Undercloud """
    def test_2_Export_Undercloud_Errors(self):
        print('\ntest_2_Export_Undercloud_Errors')
        mode_start_time = time.time()
        result_file = 'Undercloud.log'
        log_root_dir=str(undercloud_logs)
        command = "sudo python2 Extract_On_Node.py '" + str(user_start_time) + "' " + "'" + log_root_dir + "'" + " '" + grep_string + "'" + ' ' + result_file
        com_result=exec_command_line_command(command)
        shutil.move(result_file+'.gz', os.path.join(os.path.abspath(result_dir),result_file+'.gz'))
        end_time=time.time()
        if com_result['ReturnCode']==0:
            spec_print(['Completed!!!','Result Directory: '+result_dir,'Execution Time: '+str(end_time-mode_start_time)+'[sec]'],'green')
            workers_output['UndercloudNode'] = com_result['CommandOutput'].splitlines()[-2]
        else:
            spec_print(['Completed!!!', 'Result Directory: ' + result_dir,
                        'Execution Time: ' + str(end_time - mode_start_time) + '[sec]'], 'red')
        if com_result['ReturnCode']!=0:
            self.raise_warning('LogTool execution has failed to be executed on Underloud logs :-(')

    """ This test will create a Final report. The report file will be created only when ERRORs have been detected.
        Report file will be used as indication to ansible to PASS or FAIl, in case of failure it will "cat" its
        content.
    """

    def test_3_download_jenkins_job(selfself):
        # Command Line parameters
        mode_start_time=time.time()
        start_time = set_default_arg_by_index(2, '2020-07-01 00:00:00')
        artifacts_url=set_default_arg_by_index(3,'https://rhos-qe-jenkins.rhev-ci-vms.eng.rdu2.redhat.com/job/OSPD-Customized-Deployment-virt/15926/artifact/')
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
        response = urllib2.urlopen(artifacts_url)
        html = response.read()
        parsed_url = urlparse.urlparse(artifacts_url)
        base_url = parsed_url.scheme + '://' + parsed_url.netloc
        soup = BeautifulSoup(html)
        tar_gz_files = []
        ir_logs_urls = []
        tempest_log_url = None
        for link in soup.findAll('a'):
            if 'tempest-results' in link:
                tempest_results_url = urljoin(artifacts_url, link.get('href'))
                tempest_response = urllib2.urlopen(tempest_results_url)
                html = tempest_response.read()
                soup = BeautifulSoup(html)
                for link in soup.findAll('a'):
                    if str(link.get('href')).endswith('.html'):
                        tempest_html = link.get('href')
                        tempest_log_url = urljoin(artifacts_url, 'tempest-results') + '/' + tempest_html
                        break
            if str(link.get('href')).endswith('.tar.gz'):
                tar_gz_files.append(link)
                tar_link = urlparse.urljoin(artifacts_url, link.get('href'))
                os.system('wget -P ' + destination_dir + ' ' + tar_link)
            if str(link.get('href')).endswith('.sh'):
                sh_page_link = urlparse.urljoin(artifacts_url, link.get('href'))
                response = urllib2.urlopen(sh_page_link)
                html = response.read()
                soup = BeautifulSoup(html)
                for link in soup.findAll('a'):
                    if str(link.get('href')).endswith('.log'):
                        ir_logs_urls.append(sh_page_link + '/' + link.get('href'))
        # Download console.log
        console_log_url=artifacts_url.strip().replace('artifact','consoleFull').strip('/')
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



        worker_path=os.path.abspath('Extract_On_Node.py')
        print '\n'+worker_path*100



        command = "python2 "+worker_path+" '" + start_time + "' " + os.path.abspath(
            destination_dir) + " '" + grep_string + "'" + ' ' + result_file
        print_in_color(command,'green')
        print '\n'+command*100





        # shutil.copytree(destination_dir, os.path.abspath(result_dir))
        exec_command_line_command('cp -r ' + destination_dir + ' ' + os.path.abspath(result_dir))
        print_in_color('\n --> ' + command, 'bold')
        start_time = time.time()
        com_result = exec_command_line_command(command)
        # print (com_result['CommandOutput'])
        end_time = time.time()
        if com_result['ReturnCode'] == 0:
            spec_print(['Completed!!!', 'You can find the result file + downloaded logs in:',
                        'Result Directory: ' + result_dir,
                        'Analyze logs execution time: ' + str(round(end_time - mode_start_time, 2)) + '[sec]'],
                       'green')
        else:
            spec_print(['Completed!!!', 'Result Directory: ' + result_dir,
                        'Analyze logs execution time: ' + str(round(end_time - mode_start_time, 2)) + '[sec]'],
                       'red')

        def test_4_create_final_report(self):
            print('\ntest_3_create_final_report')
            report_file_name = 'LogTool_Report.log'
            if report_file_name in os.listdir('.'):
                os.remove(report_file_name)
            report_data=''

            for key in workers_output:
                if 'Total_Number_Of_Errors:0' not in workers_output[key]:
                    report_data+='\n'+key+' --> '+workers_output[key]
            if len(report_data)!=0:
                append_to_file(report_file_name,report_data+
                               '\n\nFor more details, check LogTool result files on your setup:'
                               '\n'+os.path.abspath(result_dir))
