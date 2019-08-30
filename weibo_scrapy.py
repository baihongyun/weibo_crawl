#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2018/9/4 10:38
# @Author  : 
# @File    : weibo_scrapy_core.py
# @Software: PyCharm

import os
import re
import time
import logging
import pickle
import requests
import numpy as np
from lxml import etree
from settings import config
from util.db_relate import *
from util.save_to_docx import *
from util.save_to_docx import save_to_docx
from util.save_to_docx import write_cover

# 定义正则表达式, 提取数字
pattern = re.compile('\d+')

# 初始化
mongodb = Mongodb()

class WbScrapy(object):
    def __init__(self, scrap_id):
        self.scrap_id = scrap_id
        self.filter_flag=0
        # 预先定义好
        self.rest_time = 20  # 等待时间
        self.weibo_comment_detail_urls = []  # 微博评论地址
        self.weibo_content = []  # 微博内容
        self.weibo_num_zan_list = []  # 微博点赞数
        self.weibo_num_forward_list = []  # 微博转发数
        self.weibo_num_comment_list = []  # 微博评论数
        self.weibo_scraped = 0  # 抓取的微博条数
        self.rest_min_time = 10
        self.rest_max_time = 20

        self.scrapy_mark_save_file = os.path.join(config.SCRAPED_MARK_PATH, "scraped_id.pkl") # 已经爬取的种子id的保存
        self.weibo_content_save_file = os.path.join(config.CORPUS_SAVE_DIR, 'weibo_content.pkl') # 微博内容的保存
        self.weibo_fans_save_file = os.path.join(config.CORPUS_SAVE_DIR, 'weibo_fans.pkl') # 微博粉丝的保存
        self.scrapy_ids_file = os.path.join(config.CORPUS_SAVE_DIR, 'scrapy_ids.txt')  # 爬取的种子id的保存
        self.weibo_content_comment_save_file = os.path.join(config.CORPUS_SAVE_DIR, 'weibo_content_comment.pkl')

        self.get_cookies_by_account()
        self.request_header()
        self.user_name,self.touxiang_img,self.user_brief, self.weibo_num, self.gz_num, self.fs_num, self.page_num = self.get_weibo_baisc_info()

    # 加载cookie
    def get_cookies_by_account(self):
        with open(config.COOKIE_SAVE_PATH, 'rb') as f:
            cookie = pickle.load(f)
            # 未来抓取页面需要的可不登陆的cookie
            self.cookie = {
                "Cookie": cookie[config.ACCOUNT_ID]
            }

    # 获取请求的cookie和headers
    def request_header(self):
        # 避免被禁，获取头文件
        headers = requests.utils.default_headers()
        user_agent = {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:61.0) Gecko/20100101 Firefox/61.0"
        }
        headers.update(user_agent)
        self.headers = headers

    # 判断微博id是否被抓取过
    def judge_scapy_id(self):
        if os.path.exists(self.scrapy_mark_save_file):
            with open(self.scrapy_mark_save_file, "rb") as f:
                scraped_ids = pickle.load(f)
                if self.scrap_id in scraped_ids:
                    return True
                else:
                    return False
        return False

    # 获取微博的基本信息
    def get_weibo_baisc_info(self):
        crawl_url = 'http://weibo.cn/%s?filter=%s&page=1' % (self.scrap_id, self.filter_flag)
        print("抓取的页面是: {}".format(crawl_url))
        html = requests.get(crawl_url, cookies=self.cookie, headers=self.headers).content
        selector = etree.HTML(html)

        try:
            # 获取微博名
            self.user_name = selector.xpath("//div/table//div/span[@class='ctt']/text()")[0]
            # print("user_name: ", user_name)

            #获取微博头像URL
            user_touxiang_page_url = "https://weibo.cn" + selector.xpath("//div/table/tr/td[@valign='top']/a/@href")[0]
            user_touxiang_page = requests.get(user_touxiang_page_url,cookies=self.cookie,headers=self.headers).content
            touxiang_url  = etree.HTML(user_touxiang_page).xpath("//div[@class='c']/img/@src")[0]
            self.touxiang_img = requests.get(touxiang_url,cookies=self.cookie,headers=self.headers).content

            #获取个人简介
            if len(selector.xpath("//div[@class='ut']/span[2]/text()")):
                self.user_brief = selector.xpath("//div[@class='ut']/span[2]/text()")[0]
            else:
                self.user_brief = ""

            # 总微博数
            weibo_num = selector.xpath("//div/span[@class='tc']/text()")[0]
            self.weibo_num = pattern.findall(weibo_num)[0]
            # print("weibo_num: ", weibo_num)

            # 关注数
            gz_num = selector.xpath("//div[@class='tip2']/a/text()")[0]
            self.gz_num = pattern.findall(gz_num)[0]
            # print("gz_num: ", gz_num)

            # 粉丝数
            fs_num = selector.xpath("//div[@class='tip2']/a/text()")[1]
            self.fs_num = pattern.findall(fs_num)[0]
            # print("fs_num: ", fs_num)


            print('当前新浪微博用户{}已经发布的微博数为{}, 他目前关注{}了微博用户, 粉丝数有 {}'.format(self.user_name, self.weibo_num, self.gz_num, self.fs_num))

            if selector.xpath("//*[@id='pagelist']/form/div/input[1]") is None:
                page_num = 1
            else:
                # page_num = list(selector.xpath("//*[@id='pagelist']/form/div/input[1]")[0].attrib.iteritems())
                # [('name', 'mp'), ('type', 'hidden'), ('value', '14483')]
                # 注意抓取的是字符类型
                self.page_num = int(selector.xpath("//*[@id='pagelist']/form/div/input[1]")[0].attrib["value"])
                print("总共的微博页数: ", self.page_num)
            return self.user_name, self.touxiang_img,self.user_brief,self.weibo_num, self.gz_num, self.fs_num, self.page_num
        except Exception as e:
            logging.error(e)

    # 抓取微博正文和评论并保存到word文档中
    def get_content_and_comment_to_docx(self):

        #保存用户的基本信息
        user_main_info = {}
        user_main_info["user_name"] = self.user_name
        user_main_info["touxiang_img"] = self.touxiang_img
        user_main_info["user_brief"] = self.user_brief
        user_main_info["weibo_num"] = self.weibo_num
        user_main_info["gz_num"] = self.gz_num
        user_main_info["fs_num"] = self.fs_num
        #write_cover(user_main_info)

        # 开始进行抓取, 出于简单考虑这里不考虑抓取过
        start_page = 60
        try:

            for page in range(start_page + 1, self.page_num + 1):
                url = 'http://weibo.cn/%s?filter=%s&page=%s' % (str(self.scrap_id), str(self.filter_flag), str(page))
                html_other = requests.get(url=url, cookies=self.cookie, headers=self.headers).content
                selector_other = etree.HTML(html_other)
                content = selector_other.xpath("//div[@class='c']")
                print("***************************************************")
                print("当前解析的是第{}页，总共{}页".format(page, self.page_num))
                print("微博URL："+url)
                # 每5页暂停一会，防止被禁
                if page % 5 == 0:
                    print("等待{}s，以免微博被禁！".format(self.rest_time))
                    time.sleep(self.rest_time)

                # 只有10条数据，但是抓取有12条数据，因此需要进行删除
                if len(content) > 3:
                    for i in range(0, len(content) - 2):

                        # 抓取的微博条数
                        self.weibo_scraped += 1

                        # 获取加密后的id, 方便后续提取评论等数据
                        detail = content[i].xpath("@id")[0]
                        comment_url = 'http://weibo.cn/comment/{}?uid={}&rl=0'.format(detail.split('_')[-1],                                                                                      self.scrap_id)
                        self.weibo_comment_detail_urls.append(comment_url)

                        # 点赞数
                        num_zan = content[i].xpath('div/a/text()')[-4]
                        num_zan = pattern.findall(num_zan)[0]
                        self.weibo_num_zan_list.append(num_zan)

                        # 转发数
                        num_forward = content[i].xpath('div/a/text()')[-3]
                        num_forward = pattern.findall(num_forward)[0]
                        self.weibo_num_forward_list.append(num_forward)

                        # 评论数
                        num_comment = content[i].xpath('div/a/text()')[-2]
                        num_comment = pattern.findall(num_comment)[0]
                        self.weibo_num_comment_list.append(num_comment)

                        #发表时间和微博来源
                        publication_time = content[i].xpath("div/span[@class='ct']/text()")[0]
                        if len(content[i].xpath("div/span[@class='ct']/a/text()")):
                            publication_time  = publication_time + content[i].xpath("div/span[@class='ct']/a/text()")[0]

                        # 判断全文是否展开
                        quanwen_string = content[i].xpath("div/span[@class='ctt']/a/text() | div/a/text()")
                        if "全文" in quanwen_string:
                            #quanwen_url = content[i].xpath("div/span[@class='ctt']/a[%d]/@href" % (index + 1))[0]
                            quanwen_url = content[i].xpath("div/a[contains(text(),'全文')]/@href | div/span[@class='ctt']/a[contains(text(),'全文')]/@href")[0]
                            quanwen_url = "https://weibo.cn" + quanwen_url
                            html_quanwen = requests.get(url=quanwen_url, cookies=self.cookie,
                                                        headers=self.headers).content
                            selector_quanwen = etree.HTML(html_quanwen)
                            #weibo_text = selector_quanwen.xpath("//div/div/span[@class='ctt']")[0]
                            #weibo_text = "".join(weibo_text.xpath("text()"))
                            weibo_text = ""
                            if len(selector_quanwen.xpath("//div/div/span[@class='ctt']/parent::*")):
                                weibo_text = selector_quanwen.xpath("//div/div/span[@class='ctt']/parent::*")[0]
                                weibo_text = weibo_text.xpath("string(.)")
                            if len(selector_quanwen.xpath("//div/div/span[@class='ctt']")):
                                weibo_text = selector_quanwen.xpath("//div/div/span[@class='ctt']")[0]
                                weibo_text = weibo_text.xpath("string(.)")
                            self.weibo_content.append(weibo_text)

                        else:
                            weibo_text = content[i].xpath("div/span[@class='ctt'] | div/span[@class='ctt']/following-sibling::*")[0]
                            weibo_text = weibo_text.xpath("string(.)")
                            self.weibo_content.append(weibo_text)

                        #输出微博内容
                        print("微博内容："+ weibo_text)

                        #获取图像，含三个DIV和两个DIV时有图像，一个DIV时无图像
                        ori_pictures_list = []
                        if len(content[i].xpath('div')) >=2:
                            if content[i].xpath('div[1][count(a)>=1]')  and content[i].xpath('div[1]/a[last() and contains(text(),"组图共")]'):
                                ori_pictures_page_url = content[i].xpath('div[1]/a[last()]/@href')[0]
                                ori_pictures_HTML = requests.get(url=ori_pictures_page_url, cookies=self.cookie,headers=self.headers).content
                                ori_picture_selector = etree.HTML(ori_pictures_HTML).xpath("//div")
                                for i in range(1, len(ori_picture_selector)-1):
                                    ori_picture_url = "https://weibo.cn" + ori_picture_selector[i].xpath("a[2]/@href")[0]
                                    print("图像URL："+ori_picture_url)
                                    img = requests.get(ori_picture_url, cookies=self.cookie,headers=self.headers).content
                                    ori_pictures_list.append(img)
                            elif content[i].xpath('div[2]/a[contains(text(),"原图")]'):
                                ori_pictures_page_url = content[i].xpath('div[2]/a[contains(text(),"原图")]/@href')[0]
                                img = requests.get(url=ori_pictures_page_url, cookies=self.cookie,headers=self.headers).content
                                ori_pictures_list.append(img)
                            else:
                                pass

                        #定义保存的元组数据
                        content_and_comment_dict = {}
                        content_and_comment_dict["time"] = publication_time
                        content_and_comment_dict["content"] = weibo_text
                        content_and_comment_dict["pictures"] = ori_pictures_list
                        content_and_comment_dict["url"] = comment_url
                        content_and_comment_dict["comment"] = []

                        '''
                        # 抓取评论数据
                        print("微博评论URL:"+comment_url)
                        html_detail = requests.get(comment_url, cookies=self.cookie, headers=self.headers).content
                        selector_detail = etree.HTML(html_detail)
                        comment_list = selector_detail.xpath("//div[starts-with(@id, 'C_')]")

                        # 如果当前微博没有评论，跳过它
                        if comment_list :
                            for comment in comment_list:
                                single_comment_user_name = comment.xpath("a[1]/text()")[0]
                                # count: Returns the number of nodes for a given XPath  返回指定xpath的节点数
                                if comment.xpath('span[1][count(*)=0]'):
                                    single_comment_content = comment.xpath('span[1][count(*)=0]/text()')[0]
                                    full_single_comment = '[' + single_comment_user_name + ']' + ': ' + single_comment_content
                                    content_and_comment_dict['comment'].append(full_single_comment)
                                    #打印输出评论
                                    print(full_single_comment)
                                elif comment.xpath('span[1][count(img)>0]') and len(comment.xpath('span[1][count(img)>0]/text()')):
                                    single_comment_content = comment.xpath('span[1][count(img)>0]/text()')[0]
                                    full_single_comment = '[' + single_comment_user_name + ']' + ': ' + single_comment_content
                                    content_and_comment_dict['comment'].append(full_single_comment)
                                    #打印输出评论
                                    print(full_single_comment)
                                else:
                                    single_comment_content = ''
                                    if len(comment.xpath('span[1]/text()')) >= 1:
                                        single_comment_content = single_comment_content + comment.xpath('span[1]/text()')[0]
                                    if len(comment.xpath('span[1]/a/text()')):
                                        single_comment_content = single_comment_content + comment.xpath('span[1]/a/text()')[0]
                                    if len(comment.xpath('span[1]/text()')) >= 2:
                                        single_comment_content = single_comment_content + comment.xpath('span[1]/text()')[1]
                                    full_single_comment = '[' + single_comment_user_name + ']' + ': ' + single_comment_content
                                    content_and_comment_dict['comment'].append(full_single_comment)
                                    #打印输出评论
                                    print(full_single_comment)
                        else:
                            content_and_comment_dict["comment"] = []
                        '''
                        save_to_docx(content_and_comment_dict)

        except Exception as e:
            logging.error('在获取微博内容和评论的过程中抛出异常, error:', e)
            print('\n' * 2)
            print('=' * 20)


if __name__ == "__main__":
     #wb_scrapy = WbScrapy(scrap_id=1742566624)
     #wb_scrapy = WbScrapy(scrap_id=2093192445)  1803853834
     wb_scrapy = WbScrapy(scrap_id=6006394101)
    #wb_scrapy.get_weibo_baisc_info()
    # wb_scrapy.get_weibo_content()
     wb_scrapy.get_content_and_comment_to_docx()

