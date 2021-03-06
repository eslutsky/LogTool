#!/usr/bin/python3

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

import shutil,random,datetime,threading,warnings
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
from Common import *
warnings.filterwarnings(action='ignore',module='.*paramiko.*')

### Check if updated LogTool is available ###
cur_dir=os.path.abspath('')
git_command='cd '+cur_dir+'; git pull --dry-run > git_status.txt'
cur_dir=os.path.abspath('')
git_command='cd '+cur_dir+'; git pull --dry-run'
git_result=exec_command_line_command(git_command)
if git_result['CommandOutput']!='':
    spec_print(["-------Important-------","New LogTool version is available","Use 'git pull' command to upgrade!"],'yellow')

# Parameters #
overcloud_logs_dir = '/var/log'
overcloud_ssh_user = 'heat-admin'
overcloud_ssh_key = '/home/stack/.ssh/id_rsa'
undercloud_logs = ['/var/log','/home/stack','/usr/share/','/var/lib/']
source_rc_file_path='/home/stack/'
log_storage_host='cougar11.scl.lab.tlv.redhat.com'
#log_storage_directory='/srv/static'
log_storage_directory='/rhos-infra/jenkins-logs'
overcloud_home_dir = '/home/' + overcloud_ssh_user + '/'

# On interrupt "ctrl+c" executed script will be killed
executed_script_on_overcloud = []
executed_script_on_undercloud = []
global errors_on_execution
errors_on_execution = {}

# Get all Overcloud Nodes #
is_undercloud_host=False
if os.path.isfile('/home/stack/core_puddle_version')==True:
    try:
        print_in_color('Connectivity check to all OC nodes...','bold')
        overcloud_nodes = []
        oc_nodes_command='source ' + source_rc_file_path + 'stackrc;openstack server list -f json'
        print_in_color('Trying to detect all Overcloud Nodes with:\n'+oc_nodes_command,'bold')
        all_nodes = exec_command_line_command(oc_nodes_command)['JsonOutput']
    except Exception as e:
        print_in_color('Failed to detect Overcloud Nodes :( '+str(e),'red')
        sys.exit(1)

    all_nodes = [{'Name': item['name'], 'ip': item['networks'].split('=')[-1]} for item in all_nodes]
    for node in all_nodes:
        if check_ping(node['ip']) is True:
            overcloud_nodes.append(node)
        else:
            print_in_color('Warning - ' + str(node) + ' will be skipped, due to connectivity issue!!!', 'yellow')
    if len(overcloud_nodes) == 0:
        print_in_color('No Overcloud nodes detected, looks like your OSP installation has failed!', 'red')
        sys.exit(1)

# This function is called when threads (executed on OC nodes) are being started #
def execute_on_node(**kwargs):
    print('Remote Overcloud Node -->', kwargs['Node']['Name'])
    s = SSH(kwargs['Node']['ip'], user=overcloud_ssh_user, key_path=overcloud_ssh_key)
    s.ssh_connect_key()
    if kwargs['Mode']=='Export_Range':
        result_file=kwargs['ResultFile']+'.gz' # This file will be created by worker script
        result_dir=kwargs['ResultDir']
        print('Upload script result:', s.scp_upload('Extract_Range.py', overcloud_home_dir + 'Extract_Range.py'))
        s.ssh_command('chmod 777 ' + overcloud_home_dir + 'Extract_Range.py')
        command = "sudo "+overcloud_home_dir+"Extract_Range.py '"+kwargs['StartRange']+"' '"+kwargs['StopRange']+\
                  "' "+kwargs['LogDir']+" "+kwargs['ResultFile']+' '+kwargs['ResultDir']
        print('Executed command on host --> ', command)
        com_result = s.ssh_command(command)
        print(com_result['Stdout'])  # Do not delete me!!!
        if 'SUCCESS!!!' in com_result['Stdout']:
            print_in_color(kwargs['Node']['Name'] + ' --> OK', 'green')
        else:
            print_in_color(kwargs['Node']['Name'] + ' --> FAILED', 'red')
            errors_on_execution[node['Name']] = False
        print(s.scp_download(overcloud_home_dir + result_file, os.path.join(os.path.abspath(kwargs['ModeResultDir']), result_file)))
        print(s.scp_download(overcloud_home_dir + result_dir+'.zip', os.path.join(os.path.abspath(kwargs['ModeResultDir']), result_dir+'.zip')))
        files_to_delete = ['Extract_Range.py', result_file, result_dir, result_dir+'.zip',kwargs['ResultFile']]
    if kwargs['Mode']=='Export_Overcloud_Errors':
        result_file = kwargs['Node']['Name'].replace(' ', '') + '_' + grep_string.replace(' ', '_') + '.log'
        result_dir = kwargs['ResultDir']
        print('Upload script result:',s.scp_upload('Extract_On_Node.py', overcloud_home_dir + 'Extract_On_Node.py'))
        s.ssh_command('chmod 777 ' + overcloud_home_dir + 'Extract_On_Node.py')
        command = "sudo " + overcloud_home_dir + "Extract_On_Node.py '" + str(
            start_time) + "' " + overcloud_logs_dir + " '" + grep_string + "'" + ' ' + result_file + ' ' + save_raw_data+' None '+kwargs['LogsType']
        print('Executed command on host --> ', command)
        com_result = s.ssh_command(command)
        print(com_result['Stdout'])  # Do not delete me!!!
        if 'SUCCESS!!!' in com_result['Stdout']:
            print_in_color(kwargs['Node']['Name'] + ' --> OK', 'green')
        else:
            print_in_color(kwargs['Node']['Name'] + ' --> FAILED', 'red')
            errors_on_execution[node['Name']] = False
        result_file=result_file+'.gz'
        print('Download result file result:',s.scp_download(overcloud_home_dir + result_file, os.path.join(os.path.abspath(result_dir), result_file)))
        files_to_delete = ['Extract_On_Node.py', result_file]
    if kwargs['Mode']=='Download_All_Logs':
        zip_file_name=kwargs['Node']['Name']+'.zip'
        command='sudo zip -r ' + zip_file_name +' ' + overcloud_logs_dir
        s.ssh_command(command)
        print(s.scp_download(overcloud_home_dir + zip_file_name, os.path.join(os.path.abspath(kwargs['ResultDir']), zip_file_name)))
        files_to_delete=[zip_file_name]
    if kwargs['Mode']=='GrepString':
        output_greps_file = 'All_Grep_Strings_'+kwargs['Node']['Name']+'.log'
        print(s.scp_upload('Grep_String.py', overcloud_home_dir + 'Grep_String.py'))
        print(s.ssh_command('chmod 777 ' + overcloud_home_dir + 'Grep_String.py'))
        command='sudo ' + overcloud_home_dir + 'Grep_String.py ' + overcloud_logs_dir + ' ' + string_to_grep + ' ' + output_greps_file
        print_in_color(command,'bold')
        s.ssh_command(command)
        print(s.scp_download(overcloud_home_dir + output_greps_file, os.path.join(os.path.abspath(kwargs['ResultDir']), output_greps_file)))
        files_to_delete=[output_greps_file,'Grep_String.py']
    if kwargs['Mode']=='ExecuteUserScript':
        output_file = kwargs['Node']['Name']+'.log'
        print(s.scp_upload(script_path, os.path.basename(kwargs['UserScript'])))
        print(s.ssh_command('chmod 777 ' + os.path.basename(kwargs['UserScript'])))
        command='sudo ./' + os.path.basename(kwargs['UserScript'])+' | tee '+output_file
        print('Executed command on host is: ',command)
        print_in_color(s.ssh_command_only(command)['Stdout'],'blue')
        print(overcloud_home_dir + output_file, os.path.join(os.path.abspath(kwargs['ResultDir']), output_file))
        print(s.scp_download(overcloud_home_dir + output_file, os.path.join(os.path.abspath(kwargs['ResultDir']), output_file)))
        files_to_delete=[output_file,os.path.basename(kwargs['UserScript'])]
    if kwargs['Mode']=='Download_Relevant_Logs':
        print(s.scp_upload('Download_Logs_By_Timestamp.py', overcloud_home_dir + 'Download_Logs_By_Timestamp.py'))
        print(s.ssh_command('chmod 777 ' + overcloud_home_dir + 'Download_Logs_By_Timestamp.py'))
        command="sudo " + overcloud_home_dir + "Download_Logs_By_Timestamp.py '" + str(start_time) + "' " + overcloud_logs_dir +' '+ kwargs['Node']['Name']
        print(command)
        com_result=s.ssh_command(command)
        print(com_result['Stdout']) # Do not delete me!!!
        if 'SUCCESS!!!' in com_result['Stdout']:
            print_in_color(kwargs['Node']['Name']+' --> OK','green')
        else:
            print_in_color(str(node) + ' --> FAILED','red')
            errors_on_execution[node['Name']]=False
        print(s.scp_download(overcloud_home_dir + kwargs['Node']['Name']+'.zip', os.path.join(os.path.abspath(kwargs['ResultDir']), kwargs['Node']['Name']+'.zip')))
        # Clean all #
        files_to_delete=['Download_Logs_By_Timestamp.py',kwargs['Node']['Name']+'.zip', kwargs['Node']['Name']]
    for fil in files_to_delete:
            s.ssh_command('sudo rm -rf ' + fil)
    s.ssh_close()

### Operation Modes ###
try:
    modes=['Export ERRORs/WARNINGs from Overcloud logs',
           '"Grep" some string on all Overcloud logs',
           'Extract messages for given time range',
           "Execute user's script",
           'Download Overcloud Logs',
           'Export ERRORs/WARNINGs from Undercloud logs',
           'Download Jenkins Job logs and run LogTool locally',
           'Analyze Gerrit(Zuul) failed gate logs',
           'Octavia - find Master']
    mode=choose_option_from_list(modes,'Please choose operation mode: ')

    if mode[1] == 'Analyze Gerrit(Zuul) failed gate logs':
        wget_exists=exec_command_line_command('wget -h')
        if wget_exists['ReturnCode']!=0:
            exit('WGET tool is not installed on your host, please install and rerun this operation mode!')
        # Make sure that BeutifulSoup is installed
        try:
            from bs4 import BeautifulSoup
        except Exception as e:
            print_in_color(str(e), 'red')
            print_in_color('Execute "sudo yum install python3-setuptools" to install pip3', 'yellow')
            print_in_color('Execute "pip3 install beautifulsoup4 --user" to install it!', 'yellow')
            exit('Install beautifulsoup and rerun!')
        # Make sure that requests is installed
        try:
            import requests
        except Exception as e:
            print_in_color(str(e), 'red')
            print_in_color('Execute "pip3 install requests --user" to install it!', 'yellow')
            exit('Install requests and rerun!')

        # Function to receive all Urls recursively, works slow :(
        listUrl = []
        checked_urls=[]
        def recursiveUrl(url):
            if url in checked_urls:
                return 1
            checked_urls.append(url)
            headers = {'Accept-Encoding': 'gzip'}
            try:
                page = requests.get(url, headers=headers)
                soup = BeautifulSoup(page.text, 'html.parser')
                links = soup.find_all('a')
                links = [link for link in links if 'href="' in str(links) if '<a href=' in str(link) if
                         link['href'] != '../']
            except Exception as e:
                print(e)
                links=None
            if links is None or len(links) == 0:
                listUrl.append(url)
                print(url)
                return 1;
            else:
                listUrl.append(url)
                print(url)
                for link in links:
                    recursiveUrl(url + link['href'][0:])

        # Start mode
        options = [' ERROR ', ' WARNING ']
        grep_string=choose_option_from_list(options,'Please choose debug level option: ')[1]
        destination_dir='Zuul_Log_Files'
        destination_dir=os.path.join(os.path.dirname(os.path.abspath('.')),destination_dir)
        if os.path.exists(destination_dir):
            shutil.rmtree(destination_dir)
        os.mkdir(destination_dir)
        zuul_log_url=input("Please enter Log URL, open failed gate, then you'll find it under Summary section in 'log_url'\nYour URL: ")
        mode_start_time = time.time()
        if '//storage' in zuul_log_url:
            # spec_print(['Warning - "wget -r" (recursively) cannot be used','This storage server is always responding with "gzip" content',
            #             'causing wget to download index.html only (as gzip compressed file)','Python will be used instead to export all Urls recursievly',
            #             'works a bit slow :-('],'yellow')
            recursiveUrl(zuul_log_url)
            for link in listUrl:
                #if link.endswith('log.txt.gz'):
                save_to_path=os.path.join(destination_dir,link.replace('https://','').replace('http://',''))
                exec_command_line_command('wget -P '+save_to_path+' '+link)
        else:
            # Download  Zuul log files with Wget
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36'
            download_command='wget -r --random-wait '+'"'+user_agent+'"'+' --no-parent -e robots=off -P '+destination_dir+' '+zuul_log_url
            print ('WGET is now running and recursively downloading all files...')
            return_code=exec_command_line_command(download_command)
            #if return_code['ReturnCode']!=0:
            #    print_in_color('Failed to download Zuul logs!', 'red')

        # Run LogTool analyzing
        print_in_color('\nStart analyzing downloaded OSP logs locally','bold')
        result_dir='Gerrit_Failed_Gate_'+grep_string.replace(' ','')
        if os.path.exists(os.path.abspath(result_dir)):
            shutil.rmtree(os.path.abspath(result_dir))
        result_file = os.path.join(os.path.abspath(result_dir), 'LogTool_Result_'+grep_string.replace(' ','')+'.log')
        command = "python3 Extract_On_Node.py '"+"2019-01-01 00:00:00"+"' "+os.path.abspath(destination_dir)+" '"+grep_string+"'" + ' '+result_file+" yes 'Analyze Gerrit(Zuul) failed gate logs'"
        #shutil.copytree(destination_dir, os.path.abspath(result_dir))
        exec_command_line_command('cp -r '+destination_dir+' '+os.path.abspath(result_dir))
        print_in_color('\n --> '+command,'bold')
        start_time=time.time()
        com_result=exec_command_line_command(command)
        end_time=time.time()
        if com_result['ReturnCode']==0:
            spec_print(['Completed!!!', 'You can find the result file + downloaded logs in:',
                        'Result Directory: ' + result_dir,
                        'Analyze logs execution time: ' + str(round(end_time - mode_start_time,2)) + '[sec]'], 'green')
        else:
            spec_print(['Completed!!!', 'Result Directory: ' + result_dir,
                        'Analyze logs execution time: ' + str(round(end_time - mode_start_time,2)) + '[sec]'], 'red')

    if mode[1]=='Download Jenkins Job logs and run LogTool locally':
        wget_exists=exec_command_line_command('wget -h')
        if wget_exists['ReturnCode']!=0:
            exit('WGET tool is not installed on your host, please install and rerun this operation mode!')
        # Start mode
        options = [' ERROR ', ' WARNING ']
        grep_string=choose_option_from_list(options,'Please choose debug level option: ')[1]
        start_time = input('\nEnter your "since time" to analyze log files,'
                           '\nFor example it could be start time of some failed stage'
                           '\nTime format example: 2020-04-22 12:10:00 enter your time: '
                           '\nOtherwise, press ENTER to continue: ')
        if start_time == '':
            start_time = '2019-01-01 00:00:00'
        else:
            if check_user_time(start_time)['Error']!=None:
                print('Bad time format: '+start_time+' Execution will be stopped!')
                exit(1)

        destination_dir='Jenkins_Job_Files'
        destination_dir=os.path.join(os.path.dirname(os.path.abspath('.')),destination_dir)
        create_dir(destination_dir)

        #Download log files
        options=["Download files through Jenkins Artifacts URL using HTTP", "Download files using SCP from: "+log_storage_host]
        option=choose_option_from_list(options,'Please choose your option to download files: ')
        if option[1]=='Download files through Jenkins Artifacts URL using HTTP':
            # Make sure that BeutifulSoup is installed
            try:
                from bs4 import BeautifulSoup
            except Exception as e:
                print_in_color(str(e), 'red')
                print_in_color('Execute "sudo yum install python3-setuptools" to install pip3', 'yellow')
                print_in_color('Execute "pip3 install beautifulsoup4" to install it!', 'yellow')
                exit('Install beautifulsoup and rerun!')
            artifact_url = input('Copy and paste Jenkins URL to Job Artifacts for example \nhttps://rhos-qe-jenkins.rhev-ci-vms.eng.rdu2.redhat.com/job/DFG-hardware_provisioning-rqci-14_director-7.6-vqfx-ipv4-vxlan-IR-networking_ansible/39/artifact/\nYour URL: ')

            if (artifact_url.lower().endswith('artifact') or artifact_url.lower().endswith('artifact/'))==False:
                print_in_color("Provided URL doesn't seem to be proper artifact URL, please rerun using correct URL address!"
                               "\nas given in the above example of artifact URL!",'red')
                sys.exit(1)
            # Collect log URLs to download
            mode_start_time = time.time()
            response = urllib.request.urlopen(artifact_url)
            html = response.read()
            soup = BeautifulSoup(html, 'lxml')
            tar_gz_files = []
            ir_logs_urls = []
            tempest_log_urls = []
            tobiko_log_urls = []
            all_links={}
            for link in soup.findAll('a'):
                if 'tempest-results' in link:
                    tempest_results_url = urljoin(artifact_url, link.get('href'))
                    tempest_response = urllib.request.urlopen(tempest_results_url)
                    html = tempest_response.read()
                    soup = BeautifulSoup(html)
                    for link in soup.findAll('a'):
                        if str(link.get('href')).endswith('.html'):
                            tempest_html = link.get('href')
                            tempest_log_urls.append(urljoin(artifact_url, 'tempest-results') + '/' + tempest_html)
                if 'Test Result' in link:
                    tobiko_results_url = urljoin(artifact_url, link.get('href'))
                    tobiko_link_name = link.get('href')
                    tobiko_response = urllib.request.urlopen(tobiko_results_url)
                    html = tobiko_response.read()
                    soup = BeautifulSoup(html)
                    for link in soup.findAll('a'):
                        if str(link.get('href')).startswith('tobiko.tests'):
                            tobiko_html = link.get('href')
                            tobiko_log_urls.append(urljoin(artifact_url, tobiko_link_name) + '/' + tobiko_html)
                    tobiko_log_urls = list(set(tobiko_log_urls))
                if str(link.get('href')).endswith('.tar.gz'):
                    tar_link = urljoin(artifact_url, link.get('href'))
                    tar_gz_files.append(tar_link)
                if str(link.get('href')).endswith('.sh'):
                    sh_page_link = urljoin(artifact_url, link.get('href'))
                    response = urllib.request.urlopen(sh_page_link)
                    html = response.read()
                    soup = BeautifulSoup(html)
                    for link in soup.findAll('a'):
                        if str(link.get('href')).endswith('.log'):
                            ir_logs_urls.append(sh_page_link + '/' + link.get('href'))
            console_log_url = artifact_url.strip().replace('artifact', 'consoleFull').strip('/')
            all_links = {'ConsoleLog': [console_log_url], 'TempestLogs': tempest_log_urls,
                         'InfraredLogs': ir_logs_urls, 'TarGzFiles': tar_gz_files, 'TobikoLogs': tobiko_log_urls}
            # Download logs
            for key in all_links.keys():
                for url in all_links[key]:
                    res = download_file(url, destination_dir)
                    if res['Status'] != 200:
                        print_in_color('Failed to download: ' + url, 'red')
                    else:
                        print_in_color('OK --> ' + url, 'blue')
                    if key == 'TempestLogs':
                        shutil.move(res['FilePath'], res['FilePath'].replace('.html', '.log'))
                    if key == 'ConsoleLog':
                        shutil.move(res['FilePath'], res['FilePath'] + '.log')
            spec_print(['Downloaded files:'] + os.listdir(destination_dir), 'bold')

        if option[1]=="Download files using SCP from: "+log_storage_host:
            # Make sure that Paramiko is installed
            try:
                import paramiko
            except Exception as e:
                print_in_color(str(e), 'red')
                print_in_color('Execute "pip install paramiko" to install it!', 'yellow')
                exit('Install Paramiko and rerun!')
            log_storage_user=input('SSH User - '+log_storage_host+': ')
            log_storage_password=input('SSH password - '+log_storage_host+': ')
            mode_start_time = time.time()
            s = SSH(log_storage_host, user=log_storage_user, password=log_storage_password)
            s.ssh_connect_password()
            job_name=input('Please enter Job name: ')
            job_build=input('Please enter build number: ')
            job_full_path=os.path.join(os.path.join(log_storage_host,log_storage_directory),job_name)
            job_full_path=os.path.join(job_full_path,job_build)
            dir_files=s.ssh_command('ls -ltrh '+job_full_path)['Stdout'].split('\n')
            files=[f.split(' ')[-1] for f in dir_files if f.endswith('.tar.gz')]+\
                  [f.split(' ')[-1] for f in dir_files if f.endswith('.log')]
            for fil in files:
                print_in_color('Downloading "'+fil+'"...', 'bold')
                print(s.scp_download(os.path.join(job_full_path,fil),os.path.join(destination_dir,fil)))
            s.ssh_close()

        #Unzip all downloaded .tar.gz files
        for fil in os.listdir(os.path.abspath(destination_dir)):
            if fil.endswith('.tar.gz'):
                cmd = 'tar -zxvf '+os.path.join(os.path.abspath(destination_dir),fil)+' -C '+os.path.abspath(destination_dir)+' >/dev/null'+';'+'rm -rf '+os.path.join(os.path.abspath(destination_dir),fil)
                print_in_color('Unzipping '+fil+'...', 'bold')
                os.system(cmd)

        # Run LogTool analyzing
        print_in_color('\nStart analyzing downloaded OSP logs locally','bold')
        result_dir='Jenkins_Job_'+grep_string.replace(' ','')
        if os.path.exists(os.path.abspath(result_dir)):
            shutil.rmtree(os.path.abspath(result_dir))
        result_file = os.path.join(os.path.abspath(result_dir), 'LogTool_Result_'+grep_string.replace(' ','')+'.log')
        command = "python3 Extract_On_Node.py '"+start_time+"' "+os.path.abspath(destination_dir)+" '"+grep_string+"'" + ' '+result_file
        #shutil.copytree(destination_dir, os.path.abspath(result_dir))
        exec_command_line_command('cp -r '+destination_dir+' '+os.path.abspath(result_dir))
        print_in_color('\n --> '+command,'bold')
        start_time=time.time()
        com_result=exec_command_line_command(command)
        #print (com_result['CommandOutput'])
        end_time=time.time()
        if 'SUCCESS!!!' in com_result['CommandOutput']:
            spec_print(com_result['CommandOutput'].splitlines()[-3:],'bold')
            spec_print(['Completed!!!',
                        "\nCD to Result Directory: "+os.path.basename(result_dir),
                        '\nLogTool ResultFile is: '+os.path.basename(result_file),
                        'Analyzing time: ' + str(round(end_time - mode_start_time, 2)) + '[sec]'],
                        'green')
        else:
            spec_print(['Failed to analyze logs :-(', 'Result Directory: ' + result_dir,
                        'Execution time: ' + str(round(end_time - mode_start_time, 2)) + '[sec]'],'red')

    if mode[1]=='Demo':
        wget_exists=exec_command_line_command('wget -h')
        if wget_exists['ReturnCode']!=0:
            exit('WGET tool is not installed on your host, please install and rerun this operation mode!')
        # Start mode
        options = [' ERROR ', ' WARNING ']
        grep_string=choose_option_from_list(options,'Please choose debug level option: ')[1]
        start_time = input('\nEnter your "since time" to analyze log files,'
                           '\nFor example it could be start time of some failed stage'
                           '\nTime format example: 2020-04-22 12:10:00 enter your time: '
                           '\nOtherwise, press ENTER to continue: ')
        if start_time == '':
            start_time = '2019-01-01 00:00:00'
        else:
            if check_user_time(start_time)['Error']!=None:
                print('Bad time format: '+start_time+' Execution will be stopped!')
                exit(1)
        destination_dir='Jenkins_Job_Files'
        destination_dir=os.path.join(os.path.dirname(os.path.abspath('.')),destination_dir)
        if os.path.exists(destination_dir):
            shutil.rmtree(destination_dir)
        os.mkdir(destination_dir)
        #Download log files
        log_storage_host = 'seal08.qa.lab.tlv.redhat.com'
        log_storage_directory = '/root/Demo'
        # Make sure that Paramiko is installed
        try:
            import paramiko
        except Exception as e:
            print_in_color(str(e), 'red')
            print_in_color('Execute "pip install paramiko" to install it!', 'yellow')
            exit('Install Paramiko and rerun!')
        log_storage_user=input('\nSSH User - '+log_storage_host+': ')
        log_storage_password=input('\nSSH password - '+log_storage_host+': ')
        mode_start_time = time.time()
        s = SSH(log_storage_host, user=log_storage_user, password=log_storage_password)
        s.ssh_connect_password()
        dirs=s.ssh_command("ls -l "+log_storage_directory+" | grep '^d'")['Stdout']
        print_in_color('Demo logs directories are: \n'+str(dirs))
        users=str(dirs).split('\n')
        users=[i.split(' ')[-1] for i in users if i.split(' ')[-1]!='']
        job_name=choose_option_from_list(users,"Choose your directory: ")[1]
        job_build='13'
        job_full_path=os.path.join(os.path.join(log_storage_host,log_storage_directory),job_name)
        job_full_path=os.path.join(job_full_path,job_build)
        dir_files=s.ssh_command('ls -ltrh '+job_full_path)['Stdout'].split('\n')
        files=[f.split(' ')[-1] for f in dir_files if f.endswith('.tar.gz')]+\
              [f.split(' ')[-1] for f in dir_files if f.endswith('.log')]
        for fil in files:
            print_in_color('Downloading "'+fil+'"...', 'bold')
            print(s.scp_download(os.path.join(job_full_path,fil),os.path.join(destination_dir,fil)))
        s.ssh_close()

        #Unzip all downloaded .tar.gz files
        for fil in os.listdir(os.path.abspath(destination_dir)):
            if fil.endswith('.tar.gz'):
                cmd = 'tar -zxvf '+os.path.join(os.path.abspath(destination_dir),fil)+' -C '+os.path.abspath(destination_dir)+' >/dev/null'+';'+'rm -rf '+os.path.join(os.path.abspath(destination_dir),fil)
                print_in_color('Unzipping '+fil+'...', 'bold')
                os.system(cmd)
        # Run LogTool analyzing
        print_in_color('\nStart analyzing downloaded OSP logs locally','bold')
        result_dir='Jenkins_Job_'+grep_string.replace(' ','')
        if os.path.exists(os.path.abspath(result_dir)):
            shutil.rmtree(os.path.abspath(result_dir))
        result_file = os.path.join(os.path.abspath(result_dir), 'LogTool_Result_'+grep_string.replace(' ','')+'.log')
        command = "python3 Extract_On_Node.py '"+start_time+"' "+os.path.abspath(destination_dir)+" '"+grep_string+"'" + ' '+result_file
        #shutil.copytree(destination_dir, os.path.abspath(result_dir))
        exec_command_line_command('cp -r '+destination_dir+' '+os.path.abspath(result_dir))
        print_in_color('\n --> '+command,'bold')
        start_time=time.time()
        com_result=exec_command_line_command(command)
        #print (com_result['CommandOutput'])
        end_time=time.time()
        if 'SUCCESS!!!' in com_result['CommandOutput']:
            spec_print(com_result['CommandOutput'].splitlines()[-3:],'bold')
            spec_print(['Completed!!!',
                        "\nCD to Result Directory: "+os.path.basename(result_dir),
                        '\nLogTool ResultFile is: '+os.path.basename(result_file),
                        'Analyzing time: ' + str(round(end_time - mode_start_time, 2)) + '[sec]'],
                        'green')
        else:
            spec_print(['Failed to analyze logs :-(', 'Result Directory: ' + result_dir,
                        'Execution time: ' + str(round(end_time - mode_start_time, 2)) + '[sec]'],'red')

    if mode[1]=='Export ERRORs/WARNINGs from Undercloud logs':
        undercloud_time=exec_command_line_command('date "+%Y-%m-%d %H:%M:%S"')['CommandOutput'].strip()
        start_time=choose_time(undercloud_time,'Undercloud')
        print_in_color('\nYour "since time" is set to: '+start_time,'blue')
        if check_user_time(start_time)==False:
            print_in_color('Bad timestamp format: '+start_time,'yellow')
            exit('Execution will be interrupted!')
        options=[' ERROR ',' WARNING ']
        grep_string=choose_option_from_list(options,'Please choose debug level: ')[1]
        mode_start_time=time.time()
        result_dir='Undercloud_'+grep_string.replace(' ','')
        if result_dir in os.listdir('.'):
            shutil.rmtree(result_dir)
        os.mkdir(result_dir)
        result_file='Undercloud'+'_'+grep_string.replace(' ','_')+'.log.gz'
        log_root_dir=str(undercloud_logs)
        command="sudo python3 Extract_On_Node.py '" + str(start_time) + "' " +"'"+ log_root_dir +"'"+ " '" + grep_string + "'" + ' ' + result_file
        print_in_color(command,'bold')
        executed_script_on_undercloud.append('Extract_On_Node.py')
        com_result=exec_command_line_command(command)
        shutil.move(result_file, os.path.join(os.path.abspath(result_dir),result_file))
        end_time=time.time()
        if com_result['ReturnCode']==0:
            spec_print(['Completed!!!','Result Directory: '+result_dir,'Execution Time: '+str(round(end_time - mode_start_time,2))+'[sec]'],'green')
        else:
            spec_print(['Completed!!!', 'Result Directory: ' + result_dir,
                        'Execution Time: ' + str(round(end_time - mode_start_time,2)) + '[sec]'], 'red')

    if mode[1]=='"Grep" some string on all Overcloud logs':
        print_in_color("1) You can use special characters in your string"
                       "\n2) Ignore case sensitive flag is used by default",'yellow')
        string_to_grep = "'"+input("Please enter your 'grep' string: ")+"'"
        mode_start_time = time.time()
        result_dir='All_Greped_Strings'
        if result_dir in os.listdir('.'):
            shutil.rmtree(result_dir)
        os.mkdir(result_dir)
        executed_script_on_overcloud.append('Grep_String.py')
        threads = []
        for node in overcloud_nodes:
            dic_for_thread={'Node':node,'Mode':'GrepString','ResultDir':result_dir}
            t = threading.Thread(target=execute_on_node, kwargs=dic_for_thread)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        end_time=time.time()
        spec_print(['Completed!!!','Result Directory: '+result_dir,'Execution Time: '+str(round(end_time - mode_start_time,2))+'[sec]'],'green')

    if mode[1]=='Download Overcloud Logs':
        options=['Download all logs from Overcloud nodes','Download "relevant logs" only, by given timestamp']
        option = choose_option_from_list(options, 'Please choose operation mode: ')
        if option[1]=='Download all logs from Overcloud nodes':
            mode_start_time=time.time()
            result_dir='Overcloud_Logs'
            if result_dir in os.listdir('.'):
                shutil.rmtree(result_dir)
            os.mkdir(result_dir)
            threads = []
            for node in overcloud_nodes:
                dic_for_thread={'Node':node,'Mode':'Download_All_Logs','ResultDir':result_dir}
                t = threading.Thread(target=execute_on_node, kwargs=dic_for_thread)
                threads.append(t)
                t.start()
            for t in threads:
                t.join()
            end_time=time.time()
            spec_print(['Completed!!!','Result Directory: '+result_dir,'Execution Time: '+str(round(end_time - mode_start_time,2))+'[sec]'],'green')
        if option[1]=='Download "relevant logs" only, by given timestamp':
            # Change log path if needed #
            osp_versions=['Older than OSP13?', "Newer than OSP13?"]
            if choose_option_from_list(osp_versions,'Choose your OSP Version: ')[1]=='Newer than OSP13?':
                overcloud_logs_dir=os.path.join(overcloud_logs_dir,'containers')
            random_node=random.choice(overcloud_nodes)
            s = SSH(random_node['ip'], user=overcloud_ssh_user, key_path=overcloud_ssh_key)
            s.ssh_connect_key()
            com_result=s.ssh_command('date "+%Y-%m-%d %H:%M:%S"')
            print_in_color('Current date on '+random_node['Name']+' is: '+com_result['Stdout'].strip(),'blue')
            s.ssh_close()
            print_in_color('Use the same date format as in previous output','blue')
            start_time = input('And Enter your "since time" to extract log messages: ')
            if check_user_time(start_time)['Error'] != None:
                print('Bad time format: ' + start_time + ' Execution will be stopped!')
                exit(1)
            mode_start_time=time.time()
            result_dir='Overcloud_Logs_Relevant'
            if result_dir in os.listdir('.'):
                shutil.rmtree(result_dir)
            os.mkdir(result_dir)
            threads=[]
            for node in overcloud_nodes:
                dic_for_thread={'Node':node,'Mode':'Download_Relevant_Logs','ResultDir':result_dir,'OC_LOgs+Path':overcloud_logs_dir}
                t = threading.Thread(target=execute_on_node, kwargs=dic_for_thread)
                threads.append(t)
                t.start()
            for t in threads:
                t.join()
            end_time=time.time()
            if len(errors_on_execution) == 0:
                spec_print(['Completed!!!','Result Directory: '+result_dir,'Execution Time: '+str(round(end_time - mode_start_time,2))+'[sec]'],'green')
            else:
                spec_print(['Completed!!!','Result Directory: '+result_dir,'Execution Time: '+str(round(end_time - mode_start_time,2))+'[sec]'],'red')

    if mode[1] == "Execute user's script":
        user_scripts_dir=os.path.join(os.path.abspath('.'),'UserScripts')
        user_scripts=[os.path.join(user_scripts_dir,fil) for fil in os.listdir(user_scripts_dir)]
        script_path=choose_option_from_list(user_scripts,'Choose script to execute on OC nodes:')[1]
        result_dir='Overcloud_User_Script_Result'
        if result_dir in os.listdir('.'):
            shutil.rmtree(result_dir)
        os.mkdir(result_dir)
        mode_start_time = time.time()
        executed_script_on_overcloud.append(os.path.basename(script_path))
        threads = []
        for node in overcloud_nodes:
            dic_for_thread={'Node':node,'Mode':'ExecuteUserScript','ResultDir':result_dir,'UserScript':script_path}
            t = threading.Thread(target=execute_on_node, kwargs=dic_for_thread)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        end_time=time.time()
        spec_print(['Completed!!!','Result Directory: '+result_dir,
                    'Execution Time: '+str(round(end_time - mode_start_time,2))+'[sec]'],'green')

    if mode[1]=='Export ERRORs/WARNINGs from Overcloud logs':
        random_node=random.choice(overcloud_nodes)
        s = SSH(random_node['ip'], user=overcloud_ssh_user, key_path=overcloud_ssh_key)
        s.ssh_connect_key()
        com_result=s.ssh_command('date "+%Y-%m-%d %H:%M:%S"')
        overcloud_time=com_result['Stdout'].strip()
        s.ssh_close()
        overcloud_time=com_result['Stdout'].strip()
        start_time=choose_time(overcloud_time,'Overcloud')
        print_in_color('\nYour "since time" is set to: '+start_time,'blue')
        mode_start_time = time.time()
        if check_user_time(start_time)==False:
            print_in_color('Bad timestamp format: '+start_time,'yellow')
            exit('Execution will be interrupted!')
        options=[' ERROR ',' WARNING ']
        grep_string=choose_option_from_list(options,'Please choose debug level: ')[1]
        osp_logs_only='all_logs'
        handle_all_logs=choose_option_from_list(['OSP logs only','All logs'], "Log files to analyze?")[1]
        if handle_all_logs=="OSP logs only":
            osp_logs_only='osp_logs_only'
        #save_raw_data=choose_option_from_list(['yes','no'],'Save "Raw Data" in result files?')[1]
        save_raw_data='yes'
         #result_dir='Overcloud_'+start_time+'_'+grep_string.replace(' ','_').replace(':','_').replace('\n','')
        result_dir='Overcloud_'+grep_string.replace(' ','')
        if result_dir in os.listdir('.'):
            shutil.rmtree(result_dir)
        os.mkdir(result_dir)
        errors_on_execution={}
        executed_script_on_overcloud.append('Extract_On_Node.py')
        threads = []
        for node in overcloud_nodes:
            dic_for_thread={'Node':node,'LogsType':osp_logs_only,'Mode':'Export_Overcloud_Errors','ResultDir':result_dir}
            t = threading.Thread(target=execute_on_node, kwargs=dic_for_thread)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        end_time=time.time()
        if len(errors_on_execution)==0:
            spec_print(['Completed!!!','Result Directory: '+result_dir,'Execution Time: '+str(end_time-mode_start_time)+'[sec]'],'green')
        else:
            if len(errors_on_execution) == len(overcloud_nodes):
                spec_print(['Execution has failed for all nodes :-( ',
                            'Execution Time: ' + str(round(end_time - mode_start_time,2)) + '[sec]'], 'red')
            else:
                spec_print(['Completed with failures!!!', 'Result Directory: ' + result_dir,
                            'Execution Time: ' + str(round(end_time - mode_start_time,2)) + '[sec]',
                            'Failed nodes:'] + [k for k in list(errors_on_execution.keys())], 'yellow')

    if mode[1]=='Extract messages for given time range':
        start_range_time = input('\nEnter range "start time":'
                           '\nTime format example: 2020-04-22 12:10:00 enter your time: ')
        if check_user_time(start_range_time)['Error']!=None:
            print('Bad time format: '+start_time+' Execution will be stopped!')
            exit(1)
        stop_range_time = input('\nEnter range "stop time":'
                           '\nTime format example: 2020-04-22 12:20:00 enter your time: ')
        if check_user_time(stop_range_time)['Error']!=None:
            print('Bad time format: '+start_time+' Execution will be stopped!')
            exit(1)
        mode_start_time = time.time()
        for item in [start_range_time,stop_range_time]:
            if check_user_time(item)==False:
                print_in_color('Bad timestamp format: '+item,'yellow')
                exit('Execution will be interrupted!')
        mode_result_dir='Overcloud_Exported_Time_Range'
        if os.path.exists(mode_result_dir):
            shutil.rmtree(mode_result_dir)
        os.makedirs(mode_result_dir,exist_ok=True)

        executed_script_on_overcloud.append('Extract_Range.py')
        threads = []
        for node in overcloud_nodes:
            dic_for_thread={'Node':node,
                            'Mode':'Export_Range',
                            'StartRange':start_range_time,
                            'StopRange':stop_range_time,
                            'LogDir':overcloud_logs_dir,
                            'ResultFile':node['Name']+'.log',
                            'ResultDir':node['Name'],
                            'ModeResultDir':mode_result_dir}
            t = threading.Thread(target=execute_on_node, kwargs=dic_for_thread)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        end_time=time.time()
        if len(errors_on_execution)==0:
            spec_print(['Completed!!!','Result Directory: '+mode_result_dir,'Execution Time: '+str(end_time-mode_start_time)+'[sec]'],'green')
        else:
            if len(errors_on_execution) == len(overcloud_nodes):
                spec_print(['Execution has failed for all nodes :-( ',
                            'Execution Time: ' + str(end_time-mode_start_time) + '[sec]'], 'red')
            else:
                spec_print(['Completed with failures!!!', 'Result Directory: ' + mode_result_dir,
                            'Execution Time: ' + str(end_time-mode_start_time) + '[sec]',
                            'Failed nodes:'] + [k for k in list(errors_on_execution.keys())], 'yellow')

    if mode[1]=='Octavia - find Master':
        lb_list = 'source ' + source_rc_file_path + 'overcloudrc;openstack loadbalancer list -f json'
        lb_id=exec_command_line_command(lb_list)['JsonOutput'][0]['id']
        lb_show= 'source ' + source_rc_file_path + 'overcloudrc;openstack loadbalancer show '+lb_id+' -f json'
        lb_vip=exec_command_line_command(lb_show)['JsonOutput']['vip_address']
        fip_list='source ' + source_rc_file_path + 'overcloudrc;openstack floating ip list -f json'
        lb_fip=[item['floating ip address'] for item in exec_command_line_command(fip_list)['JsonOutput'] if item['fixed ip address']==lb_vip ]



except KeyboardInterrupt:
    print_in_color("\n\n\nJust a minute, killing all tool's running scripts if any :-) ",'yellow')
    if len(executed_script_on_undercloud)!=0:
        for script in executed_script_on_undercloud:
            os.system('sudo pkill -f '+script)
    if len(executed_script_on_overcloud)!=0:
        for node in overcloud_nodes:
            print('-'*90)
            print([str(node)])
            s = SSH(node['ip'], user=overcloud_ssh_user, key_path=overcloud_ssh_key)
            s.ssh_connect_key()
            for script in executed_script_on_overcloud:
                command='sudo pkill -f '+script
                print('--> '+command)
                com_result=s.ssh_command(command)
            s.ssh_close()
