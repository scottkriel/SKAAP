classdef SKAAPclient
    
    properties
        % dirStruct
        serverDir(1,:) char      % Directory of the code files on SKAAP
        clientDir(1,:) char    % Directory on client where results are stored 
        ssh_conn                % structure containing SSH connection info
       
    end
    
    properties (Constant = true)
        HOSTNAME='146.232.220.129';
        USERNAME='pi';
        PASSWORD='skaap123'; 
    end
    
    properties (SetAccess = private)
        % Store the state the object is currently in
        STATE = struct('constructor',1,'init',1); % Default: 1 - run function, 0 - skip function
    end
    
    methods
        %% Constructor
        function obj = SKAAPclient(dirStruct)
            if obj.STATE.constructor
                p = mfilename('fullpath');
                thisDir = fileparts(p);
                % Set defaults
                if nargin < 1
                    serverDir = '$HOME/SKAAP/';
                    clientDir = [thisDir,'\results'];
                else
                    if ~isfield(dirStruct,'serverDir') || isempty(dirStruct.serverDir)
                        serverDir = '$HOME/SKAAP/';
                    else
                        serverDir = dirStruct.serverDir;
                    end
                    if ~isfield(dirStruct,'clientDir') || isempty(dirStruct.clientDir)
                        clientDir = [thisDir,'\results'];
                    else
                        clientDir = dirStruct.clientDir;
                    end
                end
                obj.serverDir = serverDir;
                obj.clientDir = clientDir;
            end
        end
        
        function obj = init(obj)
            %if required (Order should not be changed!)
            if obj.STATE.init
                if isfolder(obj.clientDir)
                    disp('===============')
                    disp('WARNING')
                    disp('---------------')
                    disp('This will delete ALL the information in the following working directory,')
                    disp(' ')
                    disp(obj.clientDir)
                    disp(' ')
                    res = input('Do you wish to continue? Y/N: ','s');
                    
                    val = true;
                    while val
                        if ismember(res,{'Y','y','N','n'})
                            val = false;
                            if ismember(res,{'N','n'})
                                error('RUN STOPPED')
                            else
                                wD = obj.clientDir;
                                rmdir(wD,'s')
                                pause(2)
                                mkdir(obj.clientDir)
                            end
                        else
                            disp(' ')
                            res = input('Enter a valid response (Y or N). Do you wish to continue? Y/N: ','s');
                        end
                    end
                else
                    mkdir(obj.clientDir)
                end
                % Configure the ssh connection
                obj.ssh_conn = ssh2_config(obj.HOSTNAME,obj.USERNAME,obj.PASSWORD);
            end
        end
        
        function [freq, mag, d] = runMeasurement(obj)
            fc = 94e06;
            command1=sprintf('cd %s; python run_measurement.py %d',obj.serverDir,fc);
            ssh2_command(obj.ssh_conn, command1);
            scp_get(obj.ssh_conn,{'time0.npy','freq.npy','data0.npy'},obj.clientDir,obj.serverDir);
            
            time=readNPY(strcat(obj.clientDir,'\time0.npy')); 
            freq=readNPY(strcat(obj.clientDir,'\freq.npy'));
            mag=readNPY(strcat(obj.clientDir,'\data0.npy'));

            d = datetime(time, 'ConvertFrom', 'posixtime','timezone','Africa/Johannesburg');

        end
        
    end
end
