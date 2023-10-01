from __future__ import print_function


import os
import json
import shutil
import imghdr
import concurrent.futures
import requests
import socket

from urllib.parse import unquote, quote
from concurrent import futures

g_headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Proxy-Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Accept-Encoding": "gzip, deflate, sdch",
    # 'Connection': 'close',
}


def baidu_get_image_url_using_api(keywords, max_number=10000, face_only=False,
                                  proxy=None, proxy_type=None):
    # url解码
    def decode_url(url):
        # print("没有解码前: ",url)
        in_table = '0123456789abcdefghijklmnopqrstuvw'
        out_table = '7dgjmoru140852vsnkheb963wtqplifca'
        translate_table = str.maketrans(in_table, out_table)    # 两个表的字符一一对应的映射关系
        # print("解码的时候的映射表: ", translate_table)

        mapping = {'_z2C$q': ':', '_z&e3B': '.', 'AzdH3F': '/'}
        for k, v in mapping.items():
            url = url.replace(k, v)
        # print("解码后:", url.translate(translate_table))    
        return url.translate(translate_table)

    base_url = "https://image.baidu.com/search/acjson?tn=resultjson_com&ipn=rj&ct=201326592"\
               "&lm=7&fp=result&ie=utf-8&oe=utf-8&st=-1"
    keywords_str = "&word={}&queryWord={}".format(
        quote(keywords), quote(keywords))
    query_url = base_url + keywords_str
    query_url += "&face={}".format(1 if face_only else 0)

    init_url = query_url + "&pn=0&rn=30"

    proxies = None
    if proxy and proxy_type:
        proxies = {"http": "{}://{}".format(proxy_type, proxy),
                   "https": "{}://{}".format(proxy_type, proxy)}

    # print("请求的基础url:", init_url)

    res = requests.get(init_url, proxies=proxies, headers=g_headers)
    init_json = json.loads(res.text.replace(r"\'", "").encode("utf-8"), strict=False)
    # print("请求基础url返回的数据:", init_json)

    total_num = init_json['listNum']
    # print("total:", total_num)

    target_num = min(max_number, total_num)
    # print("既要尽力而为,也要天意成全,能够获取到的图片数量: ", target_num)
    crawl_num = min(target_num * 2, total_num)

    crawled_urls = list()
    batch_size = 30

    with futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_list = list()

        def process_batch(batch_no, batch_size):
            image_urls = list()
            url = query_url + \
                "&pn={}&rn={}".format(batch_no * batch_size, batch_size)
            try_time = 0
            while True:
                try:
                    response = requests.get(url, proxies=proxies, headers=g_headers)
                    break
                except Exception as e:
                    try_time += 1
                    if try_time > 3:
                        print(e)
                        return image_urls
            response.encoding = 'utf-8'
            res_json = json.loads(response.text.replace(r"\'", ""), strict=False)
            for data in res_json['data']:
                # if 'middleURL' in data.keys():
                #     url = data['middleURL']
                #     image_urls.append(url)
                if 'objURL' in data.keys():
                    url = unquote(decode_url(data['objURL']))
                    if 'src=' in url:
                        url_p1 = url.split('src=')[1]
                        url = url_p1.split('&refer=')[0]
                    image_urls.append(url)
                    # print(url)
                elif 'replaceUrl' in data.keys() and len(data['replaceUrl']) == 2:
                    image_urls.append(data['replaceUrl'][1]['ObjURL'])

            return image_urls

        for i in range(0, int((crawl_num + batch_size - 1) / batch_size)):
            future_list.append(executor.submit(process_batch, i, batch_size))
        for future in futures.as_completed(future_list):
            if future.exception() is None:
                crawled_urls += future.result()
            else:
                print(future.exception())

    return crawled_urls[:min(len(crawled_urls), target_num)]


# word = input("请输入你想要下载的图片-_-:")
# image_urls = baidu_get_image_url_using_api(word, 100)
# print(image_urls)

# 我写的下载图片们的程序
# if not os.path.exists(word):
#     os.mkdir(word)
# i = 0
# for url in image_urls:
#     proxy = " "
#     try:
#         resp = requests.get(url=url, headers=g_headers, proxies={"http": proxy, "https":proxy}).content
#         name = str(i) + '.jpg'
#         file_path = f"./{word}/" + name
#         fp = open(file_path , "wb")
#         fp.write(resp)
#         print(f"第{i}张下载完毕~")
#         i += 1
#     except Exception as e:
#         print(f"下载第{i}个文件的时候出现异常: ",e)
# print("下载完毕-_-")


def download_image(image_url, dst_dir, file_name, timeout=20, proxy_type=None, proxy=None):
    proxies = None
    if proxy_type is not None:
        proxies = {
            "http": proxy_type + "://" + proxy,
            "https": proxy_type + "://" + proxy
        }

    response = None
    file_path = os.path.join(dst_dir, file_name)
    try_times = 0
    while True:
        try:
            try_times += 1
            response = requests.get(image_url, headers=g_headers, timeout=timeout, proxies=proxies)
            with open(file_path, 'wb') as f:
                f.write(response.content)
            response.close()
            file_type = imghdr.what(file_path)
            # if file_type is not None:
            if file_type in ["jpg", "jpeg", "png", "bmp", "webp"]:
                new_file_name = "{}.{}".format(file_name, file_type)
                new_file_path = os.path.join(dst_dir, new_file_name)
                shutil.move(file_path, new_file_path)
                print("## OK:  {}  {}".format(new_file_name, image_url))
            else:
                os.remove(file_path)
                print("## Err: TYPE({})  {}".format(file_type, image_url))
            break
        except Exception as e:
            if try_times < 3:
                continue
            if response:
                response.close()
            print("## Fail:  {}  {}".format(image_url, e.args))
            break


def download_images(image_urls, dst_dir, file_prefix="img", concurrency=50, timeout=20, proxy_type=None, proxy=None):
    """
    Download image according to given urls and automatically rename them in order.
    :param timeout:
    :param proxy:
    :param proxy_type:
    :param image_urls: list of image urls
    :param dst_dir: output the downloaded images to dst_dir
    :param file_prefix: if set to "img", files will be in format "img_xxx.jpg"
    :param concurrency: number of requests process simultaneously
    :return: none
    """

    socket.setdefaulttimeout(timeout)

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_list = list()
        count = 0
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        for image_url in image_urls:
            file_name = file_prefix + "_" + "%04d" % count
            future_list.append(executor.submit(
                download_image, image_url, dst_dir, file_name, timeout, proxy_type, proxy))
            count += 1
        concurrent.futures.wait(future_list, timeout=180)

word = input("请输入想要搜索的图片关键字: ")
nums = input("请输入想要下载的图片数量呀: ")
nums = int(nums)
image_urls = baidu_get_image_url_using_api(word, nums)
download_path = f"./{word}/"
download_images(image_urls, download_path)
print("下载完毕")