import datetime
import matplotlib.pyplot as plt
import pandas
import sys

def generate_plots_from_csv_file(metrics_csv_file, metrics_plot_file):
    """Generate plots of the metrics collected in the .csv file

    Parameters
    ----------
    metrics_csv_file: str
        Path to input csv file.
    metrics_plot_file: str
        Path to output plot file. Matplotlib will use the extension to determine saved format.
    """

    columns = "SECONDS,Name,PIDs,CPU,Memory,MemoryP,NetSend,NetRecv,DiskRead,DiskWrite,Disk,Swap,Threads"
    convert = {'SECONDS':int(),'Name':str(),'PIDs':int(),'CPU':float(),'Memory':float(),
               'MemoryP':float(),'NetSend':float(),'NetRecv':float(),'DiskRead':float(),
               'DiskWrite':float(),'Disk':int(),'Swap':int(),'Threads':int()}

    # read in the new data and make lists out of the columns for analysis
    colnames = columns.split(',')

    data = pandas.read_csv(metrics_csv_file, header=1, names=colnames, converters=convert)

    # convert non-string data to numbers
    data = data.apply(pandas.to_numeric, errors='coerce')
    secs = data.SECONDS.tolist()
    pids = data.PIDs.tolist()
    cpu = data.CPU.tolist()
    mem = data.Memory.tolist()
    mem_p = data.MemoryP.tolist()
    net_s = data.NetSend.tolist()
    net_r = data.NetRecv.tolist()
    disk_r = data.DiskRead.tolist()
    disk_w = data.DiskWrite.tolist()
    disk = data.Disk.tolist()
    swap = data.Swap.tolist()
    threads = data.Threads.tolist()

    # determine max values
    max_pids = max(pids)
    max_cpu = max(cpu)
    max_mem = max(mem)
    max_mem_p = max(mem_p)
    max_net_s = max(net_s)
    max_net_r = max(net_r)
    max_disk_r = max(disk_r)
    max_disk_w = max(disk_w)
    max_disk = round(max(disk), 2)
    min_disk = min(disk)
    max_swap = max(swap)
    max_threads = max(threads)

    duration_s = secs[-1]
    duration_hms = str(datetime.timedelta(seconds=duration_s))

    disk_used = round(max_disk - min_disk, 2)

    # create list of plots to create
    pl = [
        {
            'y' : pids,
            'title' : 'Container Process IDs (max {})'.format(max_pids),
            'xlabel' : 'Seconds',
            'ylabel' : '# Processes'
        },
        {
            'y' : threads,
            'title' : 'Host System Threads (max {})'.format(max_threads),
            'xlabel' : 'Seconds',
            'ylabel' : '# Threads'
        },
        {
            'y' : cpu,
            'title' : 'Container CPU % (max {})'.format(max_cpu),
            'xlabel' : 'Seconds',
            'ylabel' : 'CPU % Usage'
        },
        {
            'y' : mem,
            'title' : 'Container Memory (max {:.2f} GB)'.format(max_mem),
            'xlabel' : 'Seconds',
            'ylabel' : 'Memory GB'
        },
        {
            'y' : mem_p,
            'title' : 'Container Memory %',
            'xlabel' : 'Seconds',
            'ylabel' : 'Memory %'
        },
        {
            'y' : swap,
            'title' : 'Host System Swap Used (max {} GB)'.format(max_swap),
            'xlabel' : 'Seconds',
            'ylabel' : 'Swap Used GB'
        },
        {
            'y' : disk,
            'title' : 'Host System Disk, max {} GB (Container start/end delta {} GB)'.format(max_disk, disk_used),
            'xlabel' : 'Seconds',
            'ylabel' : 'Disk GB'
        },
        {
            'y' : disk_r,
            'title' : 'Container Disk Read',
            'xlabel' : 'Seconds',
            'ylabel' : 'Disk Read GB'
        },
        {
            'y' : disk_w,
            'title' : 'Container Disk Write',
            'xlabel' : 'Seconds',
            'ylabel' : 'Disk Write GB'
        },
        {
            'y' : net_r,
            'title' : 'Container Net Recv',
            'xlabel' : 'Seconds',
            'ylabel' : 'Net Recv GB'
        },
        {
            'y' : net_s,
            'title' : 'Container Net Send',
            'xlabel' : 'Seconds',
            'ylabel' : 'Net Send GB'
        }
    ]

    # create figure with plots of data
    plot_width = 12
    plot_height = 5
    fig, axs = plt.subplots(len(pl), figsize=(plot_width, plot_height*(len(pl))))
    fig.suptitle(metrics_csv_file)
    x = secs

    for i in range(len(pl)):
        y = pl[i]['y']
        axs[i].set_title(pl[i]['title'])
        axs[i].grid(True)
        axs[i].plot(x,y,'.-')
        axs[i].set(xlabel=pl[i]['xlabel'],ylabel=pl[i]['ylabel'])

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(metrics_plot_file)


if __name__ == "__main__":

    metrics_csv_file = sys.argv[1]
    metrics_plot_file = sys.argv[2]

    generate_plots_from_csv_file(metrics_csv_file, metrics_plot_file)
