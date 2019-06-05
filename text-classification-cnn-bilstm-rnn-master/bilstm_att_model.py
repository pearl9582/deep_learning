# coding: utf-8

import tensorflow as tf


class TCNNConfig():
    """CNN配置参数"""
    dropoutKeepProb = 0.5
    l2RegLambda = 0.0

    embedding_dim = 200  # 词向量维度
    seq_length = 600  # 序列长度
    num_classes = 8  # 类别数
    num_filters = 128  # 卷积核数目
    kernel_sizes = [5, 3]  # 卷积核尺寸
    vocab_size = 5000  # 词汇表达小

    hidden_dim = 128  # 全连接层神经元
    hiddenSizes = [256, 128]  # LSTM结构的神经元个数
    dropout_keep_prob = 0.5  # dropout保留比例
    learning_rate = 1e-3  # 学习率
    l2RegLambda = 0.0
    batch_size = 64  # 每批训练大小
    num_epochs = 20  # 总迭代轮次
    hiddenSizes = [256, 256]  # 单层LSTM结构的神经元个数
    print_per_batch = 100  # 每多少轮输出一次结果
    save_per_batch = 10  # 每多少轮存入tensorboard
    train_filename = './data/cnews/cnews.cnews.test.txt'  # 训练数据train data
    test_filename = './data/cnews/cnews.cnews.val.txt'  # 测试数据test data
    val_filename = './data/cnews/cnews.cnews.val.txt'  # 验证集validation data
    vocab_filename = './data/cnews/vector_word.txt'  # vocabulary词汇集6000
    vector_word_filename = './data/cnews/vector_word.txt'  # vector_word trained by word2vec 经过word2vec训练后的词向量
    vector_word_npz = './data/cnews/vector_word.npz'  # save vector_word to numpy file


class BiLSTM(object):
    """文本分类，CNN模型"""
    """
        Bi-LSTM 用于文本分类
        """

    def __init__(self, config):
        # 定义模型的输入
        self.config = config
        self.inputX = tf.placeholder(tf.int32, shape=[None, self.config.seq_length], name='input_x')
        self.inputY = tf.placeholder(tf.float32, shape=[None, self.config.num_classes], name='input_y')

        self.dropoutKeepProb = tf.placeholder(tf.float32, name="dropoutKeepProb")

        # 定义l2损失
        l2Loss = tf.constant(0.0)

        # 词嵌入层
        with tf.name_scope("embedding"):
            # 利用预训练的词向量初始化词嵌入矩阵
            self.W = tf.get_variable('embedding', [self.config.vocab_size, self.config.embedding_dim])
            # self.W = tf.Variable(tf.cast(wordEmbedding, dtype=tf.float32, name="word2vec"), name="W")
            # 利用词嵌入矩阵将输入的数据中的词转换成词向量，维度[batch_size, sequence_length, embedding_size]
            self.embeddedWords = tf.nn.embedding_lookup(self.W, self.inputX)

        # 定义两层双向LSTM的模型结构
        with tf.name_scope("Bi-LSTM"):
            for idx, hiddenSize in enumerate(self.config.hiddenSizes):
                with tf.name_scope("Bi-LSTM" + str(idx)):
                    # 定义前向LSTM结构
                    lstmFwCell = tf.nn.rnn_cell.DropoutWrapper(
                        tf.nn.rnn_cell.LSTMCell(num_units=hiddenSize, state_is_tuple=True),
                        output_keep_prob=self.dropoutKeepProb)
                    # 定义反向LSTM结构
                    lstmBwCell = tf.nn.rnn_cell.DropoutWrapper(
                        tf.nn.rnn_cell.LSTMCell(num_units=hiddenSize, state_is_tuple=True),
                        output_keep_prob=self.dropoutKeepProb)

                    # 采用动态rnn，可以动态的输入序列的长度，若没有输入，则取序列的全长
                    # outputs是一个元祖(output_fw, output_bw)，其中两个元素的维度都是[batch_size, max_time, hidden_size],fw和bw的hidden_size一样
                    # self.current_state 是最终的状态，二元组(state_fw, state_bw)，state_fw=[batch_size, s]，s是一个元祖(h, c)
                    outputs, self.current_state = tf.nn.bidirectional_dynamic_rnn(lstmFwCell, lstmBwCell,
                                                                                  self.embeddedWords, dtype=tf.float32,
                                                                                  scope="bi-lstm" + str(idx))

                    # 对outputs中的fw和bw的结果拼接 [batch_size, time_step, hidden_size * 2]
                    self.embeddedWords = tf.concat(outputs, 2)

        # 将最后一层BiLSTM的输出结果分割成前向和后向输出
        outputs = tf.split(self.embeddedWords, 2, -1)
        print(outputs)
        with tf.name_scope("Attention"):
            H = outputs[0] + outputs[1]
            print('123',H)
            # 得到Attention的输出
            output = self.attention(H)
            outputSize = self.config.hiddenSizes[-1]
        # 全连接层的输出
        with tf.name_scope("output"):
            outputW = tf.get_variable(
                "outputW",
                shape=[outputSize, 1],
                initializer=tf.contrib.layers.xavier_initializer())

            outputB = tf.Variable(tf.constant(0.1, shape=[1]), name="outputB")
            l2Loss += tf.nn.l2_loss(outputW)
            l2Loss += tf.nn.l2_loss(outputB)
            self.predictions = tf.nn.xw_plus_b(output, outputW, outputB, name="predictions")
            self.binaryPreds = tf.cast(tf.greater_equal(self.predictions, 0.5), tf.float32, name="binaryPreds")
            # self.logits = tf.layers.dense(output, self.config.num_classes, name='logits')  # 全连接到10维的标签
            # self.prob = tf.nn.softmax(self.logits)  # 计算概率
            # self.y_pred_cls = tf.argmax(tf.nn.softmax(self.logits), 1)  # 最大的那个概率，即为标签

        # 计算二元交叉熵损失
        with tf.name_scope("loss"):
            losses = tf.nn.sigmoid_cross_entropy_with_logits(logits=self.predictions, labels=self.inputY)
            self.loss = tf.reduce_mean(losses) + self.config.l2RegLambda * l2Loss
            self.optim = tf.train.AdamOptimizer(learning_rate=self.config.learning_rate).minimize(self.loss)
        with tf.name_scope("accuracy"):
            # 准确率
            correct_pred = tf.equal(tf.argmax(self.inputY, 1), self.binaryPreds)
            self.acc = tf.reduce_mean(tf.cast(correct_pred, tf.float32))

    def attention(self, H):
        """
        利用Attention机制得到句子的向量表示
        """
        # 获得最后一层LSTM的神经元数量
        hiddenSize = self.config.hiddenSizes[-1]

        # 初始化一个权重向量，是可训练的参数
        W = tf.Variable(tf.random_normal([hiddenSize], stddev=0.1))

        # 对Bi-LSTM的输出用激活函数做非线性转换
        M = tf.tanh(H)

        # 对W和M做矩阵运算，W=[batch_size, time_step, hidden_size]，计算前做维度转换成[batch_size * time_step, hidden_size]
        # newM = [batch_size, time_step, 1]，每一个时间步的输出由向量转换成一个数字
        newM = tf.matmul(tf.reshape(M, [-1, hiddenSize]), tf.reshape(W, [-1, 1]))

        # 对newM做维度转换成[batch_size, time_step]
        restoreM = tf.reshape(newM, [-1, self.config.seq_length])

        # 用softmax做归一化处理[batch_size, time_step]
        self.alpha = tf.nn.softmax(restoreM)

        # 利用求得的alpha的值对H进行加权求和，用矩阵运算直接操作
        r = tf.matmul(tf.transpose(H, [0, 2, 1]), tf.reshape(self.alpha, [-1, self.config.seq_length, 1]))

        # 将三维压缩成二维sequeezeR=[batch_size, hidden_size]
        sequeezeR = tf.squeeze(r)

        sentenceRepren = tf.tanh(sequeezeR)

        # 对Attention的输出可以做dropout处理
        output = tf.nn.dropout(sentenceRepren, self.dropoutKeepProb)
        print("111",output)
        return output
