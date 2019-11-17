# General
It's not an easy stuff to pass through OSP logs and to find out the particular ERROR/WARNING message that
could probably be the "root cause" of problem you've encountered on your Setup and might want to investigate.
If that's the case, this tool will make your "life" much more easier, at least it will reduce the time you'll need to spent on "donkey work" to acomplish the same manually.
This tool is a set of Python script and its main module is running on Undercloud host.
There are also operation modes when additional scripts are executed directly on Overcloud nodes, for example: "Export ERRORs/WARNINGs from Overcloud logs"

**Note**: there are two different versions available: LogTool_Python2 and LogTool_Python3, make sure to CD into the correct directory.

# Operation modes

**1) Export ERRORs/WARNINGs from Overcloud logs**

This mode exports all ERRORs/WARNINGs messages that occurred since given by user timestamp.
For example, if something went wrong in the last 10 minutes you'll be able to run the tool for this time period only.
This operation mode generates result file per Overcloud node with "Table of content (Section name --> Line number)",  where you'll find:
1) Raw Data - extracted Errors/Warnings from standard OSP logs since: <Given Timestamp>
2) Skipped logs - no debug level string (Error, Info, Debug...) has been detected
3) Statistics - Number of Errors/Warnings per standard OSP log since: <Given Timestamp>
4) Statistics - Unique(Fuzzy Matching per standard OSP log file since: <Given Timestamp>
5) Statistics - Unique messages per NOT STANDARD log file, since ever


Result file is created for each Overcloud node and "Statistic sections" are generated in it.

Follow "Table of content" at the end of the file to get sections' start line indexes.

**2) Download all logs from Overcloud nodes**

Logs from all Overcloud nodes will be compressed and downloaded to local directory on your Undercloud host.

**3) "Grep" some string for all Overcloud logs**

This mode will "grep" some string (given by user) on all Overcloud logs. For example, you might want to see all loged messages for specific request ID, let's say the request ID of "Create VM" that is failed.

**4) Check current:CPU,RAM and Disk on Overcloud**

This mode will display the current: CPU, RAM and Disk info, on each Overcloud node.

**5) Export ERRORs/WARNINGs from Undercloud logs**

This mode is the same as #1, the only difference is that it will use Undercloud logs.

**6) Download "relevant logs" only, by given timestamp**

This mode will download the only Overcloud logs with *"Last Modified" > "given by user timestamp"*.
For example if you got some error 10 minutes ago, you'll probably need to investigate the actual logs only, it means that old logs won't be relevant to you and therefore download such log files is unecessary.
In addition, on Bugzila you can attach file only if its size is less than 21MB, so this mode might help.

**7) Execute user's script**

This mode provides user the ability to run his own script on Overcloud nodes.
Create your own script and save it in UserScripts directory, set proper interpreter in it (for example: #!/usr/bin/bash).

**8)  Install Python FuzzyWuzzy on Nodes**

For better performance using Python FuzzyWuzzy module on Overcloud nodes is necessary.
This mode will install FuzzyWuzzy on Overcloud nodes.

**11)  Download OSP logs and run LogTool locally**

This mode applies you to download OSP logs from Jenkins or Log Storage (cougar11.scl.lab.tlv.redhat.com) and to analyze downloaded logs locally.

**12)  Undercloud - analyze deployment log**

This mode may help you to understand what went wrong while OC or UC deployment, basing on generated log.
Deployment logs are generated when ""--log" option is used, for example inside the "overcloud_deploy.sh" script, the
problem is that such logs are not "friendly" and it's hard to understand what exactly went wrong, especially
when verbosity is set to "vv" or more, this will make the log not readable with a bunch of data inside it.
This mode will provide you some details about all failed TASKs.

# Installation
This tool is available on GitHub, clone it to your **Undercloud** host with:

    git clone https://github.com/zahlabut/LogTool.git

**Note**: some external python modules are used by tool:

1)_Paramiko_ - SSH module

This module is usually installed on Undercloud by default
Use **"ls -a /usr/lib/python2.7/site-packages | grep paramiko"** command to verify that.
Follow "Install Paramiko" section if you don't have this module installed.

2)_FuzzyWuzzy_ - string matching

This module is not mandatory, as Python has its own built in module that is used by default, but!!!
For best performance my suggestion is to use FuzzyWuzzy, follow "Install FuzzyWuzzy" section if you find it relevant.

3)_BeautifulSoup_ - HTML parser
This module is used in #11 only, where Log files are downloaded using HTTP and it's used to parse the Artifacts HTML
page to get all links in it. Follow "Install BeautifulSoup" section to install it


# Configuration
All required parameters are set directly inside PyTool.py script, defaults are:

    overcloud_logs_dir = '/var/log/containers'
    overcloud_ssh_user = 'heat-admin'
    overcloud_ssh_key = '/home/stack/.ssh/id_rsa'
    undercloud_logs_dir ='/var/log/containers'
    source_rc_file_path='/home/stack/'



# Usage
This tool is interactive, so all you have to do is to start it with:

    cd LogTool
    python PyTool.py

# Install Paramiko
On your Undercloud execute the following commands:

    sudo easy_install pip
    sudo pip install paramiko==2.1.1

# Install FuzzyWuzzy
   To install on **Undercloud** :

     sudo easy_install pip
     sudo pip install fuzzywuzzy
   To install on **Overcloud** Nodes:
   Use tool's dedicated mode **"Install Python FuzzyWuzzy on Nodes"**

     cd LogTool
     python PyTool.py

# Install BeutifulSoup

     pip install beautifulsoup4

# Troubleshooting
There are two log files created on runtime: _"Error.log"_ and _"Runtime.log"_.
Please add the content of both into the description of issue you'd like to open.


