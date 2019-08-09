#!/usr/bin/python3
""" msg_pclean module: base module for propagation tests and cleanup for Sarracenia components (in flow test)
"""


class Msg_Pclean(object):
    """ Base plugin class that is used in shovel pclean_f9x:

     - it checks if the propagation was ok.
     - it randomly set a test in the watch f40.conf for propagation
     - it posts the product again (more test in shovel clean_f91) which is propagated too
     - it remove the original product

    It also uses a file delay to tolerate a maximum lag for the test

    The posted message contains a tag in the header for the test performed which is the extension used for the test
    """
    def __init__(self, parent):
        self.test_extension_list = ['.slink', '.hlink', '.moved']
        self.ext_key = 'pclean_ext'
        self.all_fxx_dirs = ['',  # sarra f20
                             'downloaded_by_sub_t',  # subscribe amqp f30
                             # f40 is watch... no file
                             'sent_by_tsource2send',  # subscribe rabbitmqtt f50
                             'downloaded_by_sub_u',  # subscribe sub_u f60
                             'downloaded_by_sub_cp',  # subscribe sub_cp f61
                             'posted_by_shim',  # shim f63
                             'posted_by_srpost_test2',  # subscribe ftp_f70
                             'recd_by_srpoll_test1']   # subscribe q_f71

    @staticmethod
    def build_path_dict(root, fxx_dirs, relpath, ext=''):
        """ This build paths necessary to pclean tests

        It is a subset of all flow test path based on fxx download directory provided.

        :param root: usually the sarra dev doc root directory
        :param fxx_dirs: a list of the flow test directory needed
        :param relpath: the relative path of the file (starting with the date) without the forward slash
        :param ext: the extension from the extension test (optional)
        :return: a dictionnary of all paths built
        """
        import os

        results = {}
        for fxx_dir in fxx_dirs:
            results["{}{}".format(fxx_dir, ext)] = os.path.join(root, fxx_dir, "{}{}".format(relpath, ext))
        return results

    def get_extension(self, msg):
        """ Check whether the extension is in the header

        :param msg: the msg used for the test
        :return: the value corresponding to the extension key in the msg header
        """
        if self.ext_key in msg.headers:
            return msg.headers[self.ext_key]
        else:
            return None

    def log_msg_details(self, parent):
        parent.logger.error("message received is incorrect")
        msg_params = (parent.msg.pubtime, parent.msg.baseurl, parent.msg.relpath, parent.msg.topic,
                      parent.msg.get_elapse_pubtime(), parent.msg.hdrstr)
        parent.logger.error("msg_log received: {} {}{} topic={} lag={:.3f} {}".format(*msg_params))