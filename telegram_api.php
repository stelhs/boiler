<?php

function conf_telegram_bot()
{
    static $config = NULL;
    if (!is_array($config))
        $config = parse_json_config('.telegram.json');

    return $config;
}


class Telegram_api {
    private $last_update_id;

    function __construct()
    {
        $this->last_update_id = 0;
    }

    function post_request($method_name, $params = [])
    {
        $full_url = sprintf('https://api.telegram.org/bot%s/%s',
                                    conf_telegram_bot()['token'], $method_name);

        $query = http_build_query($params);

        $options = array(
            'http' => array(
                'header'  => "Content-Type: application/x-www-form-urlencoded\r\n",
                'method'  => 'POST',
                'content' => $query,
                'timeout' => 45,
            )
        );
        $context = stream_context_create($options);
        @$result = file_get_contents($full_url, false, $context);
        if ($result == FALSE)
            return -EPARSE;

        return json_decode($result, true);
    }

    function get_last_update_id()
    {
        if (!$this->last_update_id)
            @$this->last_update_id = file_get_contents(getenv("HOME") .
                                                       '/.telegram_last_update_id');
        return $this->last_update_id;
    }

    function set_last_update_id($last_update_id)
    {
        file_put_contents(getenv("HOME") . '/.telegram_last_update_id', $last_update_id);
        $this->last_update_id = $last_update_id;
    }

    function get_new_messages()
    {
        $last_update_id = $this->get_last_update_id();
        $resp = $this->post_request('getUpdates', ['offset' => $last_update_id + 1,
                                                   'limit' => 10,
                                                   'timeout' => 30]);
        if (!is_array($resp)) {
            perror("telegram: Can't make POST request %s\n", $resp);
            return $resp;
        }

        if ($resp['ok'] != 1) {
            perror("telegram: error POST request, ok=%s", $resp['ok']);
            return -EBUSY;
        }

        if (!count($resp['result']))
            return [];

        $list_msg = [];
        foreach ($resp['result'] as $row) {
            if (!isset($row['update_id']))
                continue;

            $this->set_last_update_id($row['update_id']);

            if (!isset($row['message']))
                continue;

            if (!isset($row['message']['text']))
                continue;

            perror("Processed message: %d\n", $row['message']['message_id']);
            $msg = ['update_id' =>   $row['update_id'],
                    'msg_id' =>      $row['message']['message_id'],
                    'date' =>        $row['message']['date'],
                    'from_name' =>   $row['message']['from']['first_name'],
                    'from_id' =>     $row['message']['from']['id'],
                    'chat_id' =>     $row['message']['chat']['id'],
                    'chat_type' =>   $row['message']['chat']['type'],
                    'chat_name' =>   ($row['message']['chat']['type'] == 'private' ?
                                              $row['message']['chat']['first_name'] :
                                              $row['message']['chat']['title']),
                    'text'      =>   $row['message']['text'],
            ];

            db()->insert('telegram_msg', $msg);
            $list_msg[] = $msg;
        }

        return $list_msg;
    }

    function send_message($chat_id, $text,
                $reply_to_message_id = 0, $disable_notification = false)
    {
        $params = ['chat_id' => $chat_id, 'text' => $text];
        if ($reply_to_message_id)
            $params['reply_to_message_id'] = $reply_to_message_id;
        if ($disable_notification)
            $params['disable_notification'] = $disable_notification;

        $resp = $this->post_request('sendMessage', $params);
        if (!is_array($resp)) {
            perror("telegram: Can't make POST request %s\n", $resp);
            return $resp;
        }

        if ($resp['ok'] != 1) {
            perror("telegram: error POST request, ok=%s\n", $resp['ok']);
            return -EBUSY;
        }

        return 0;
    }
}

