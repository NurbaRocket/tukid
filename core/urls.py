from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('search/', views.search, name='search'),
    path('about/', views.information_page, {'slug': 'about'}, name='about'),
    path('about/mission/', views.information_page, {'slug': 'mission'}, name='mission'),
    path('about/board/', views.information_page, {'slug': 'board'}, name='board'),
    path('membership/', views.membership, name='membership'),
    path('membership/sent/', views.membership_success, name='membership_success'),
    path('members/', views.member_list, name='members'),
    path('members/<slug:slug>/', views.member_detail, name='member_detail'),
    path('news/', views.news_list, name='news'),
    path('news/tukid/', views.news_list, {'tukid_only': True}, name='tukid_news'),
    path('news/posts/<slug:slug>/', views.news_detail, name='news_detail'),
    path('events/', views.event_list, name='events'),
    path('events/upcoming/', views.event_list, {'period': 'upcoming'}, name='upcoming_events'),
    path('events/past/', views.event_list, {'period': 'past'}, name='past_events'),
    path('events/details/<slug:slug>/', views.event_detail, name='event_detail'),
    path('meetings/', views.meeting_list, name='meetings'),
    path('meetings/<slug:slug>/', views.meeting_detail, name='meeting_detail'),
    path('career/', views.career, name='career'),
    path('career/sent/', views.career_success, name='career_success'),
    path('career/vacancies/<slug:slug>/', views.vacancy_detail, name='vacancy_detail'),
    path('contacts/', views.information_page, {'slug': 'contacts'}, name='contacts'),
    path('pages/<slug:slug>/', views.information_page, name='page'),
]
