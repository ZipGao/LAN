import tensorflow as tf
import numpy as np

class GNN_MEAN(object):
    def __init__(self, num_relation, embedding_dim):
        self.embedding_dim = embedding_dim
        self.num_relation = num_relation
        self.mlp_w = tf.compat.v1.get_variable(
                name='mlp_w',
                shape=[self.num_relation * 2 + 1, self.embedding_dim],
                initializer=tf.compat.v1.keras.initializers.VarianceScaling(scale=1.0, mode="fan_avg", distribution=("uniform" if True else "truncated_normal"))
            )

        self.l2_regularization = tf.nn.l2_loss(self.mlp_w)

    def _projection(self, e, n):
        norm = tf.nn.l2_normalize(n, 2)
        return e - tf.reduce_sum(input_tensor=e * norm, axis=2, keepdims = True) * norm

    def __call__(self, input, input_relation):
        # input: [batch, len, emb]
        projection = tf.nn.embedding_lookup(params=self.mlp_w, ids=input_relation)
        output = self._projection(input, projection)
        return tf.reduce_mean(input_tensor=output, axis=-2), 0

class LSTM(object):
    def __init__(self, num_relation, embedding_dim):
        self.embedding_dim = embedding_dim
        self.num_relation = num_relation
        self.mlp_w = tf.compat.v1.get_variable(
                name='mlp_w',
                shape=[self.num_relation * 2 + 1, self.embedding_dim],
                initializer=tf.compat.v1.keras.initializers.VarianceScaling(scale=1.0, mode="fan_avg", distribution=("uniform" if True else "truncated_normal"))
            )

        self.rnn_cell = tf.compat.v1.nn.rnn_cell.LSTMCell(self.embedding_dim)
        self.l2_regularization = tf.nn.l2_loss(self.mlp_w)

    def _projection(self, e, n):
        norm = tf.nn.l2_normalize(n, 2)
        return e - tf.reduce_sum(input_tensor=e * norm, axis=2, keepdims = True) * norm

    def __call__(self, input, input_relation):
        # input: [batch, len, emb]
        input_shape = input.shape
        batch_size = input_shape[0].value
        max_len = input_shape[1].value
        hidden_size = input_shape[2].value

        projection = tf.nn.embedding_lookup(params=self.mlp_w, ids=input_relation)
        hidden = self._projection(input, projection)

        outputs, state = tf.compat.v1.nn.dynamic_rnn(
                                self.rnn_cell,
                                hidden,
                                dtype=tf.float32)

        return tf.reduce_mean(input_tensor=outputs, axis=-2), None

class ATTENTION(object):
    """docstring for Attention"""
    def __init__(self, num_relation, num_entity, embedding_dim):
        self.embedding_dim = embedding_dim 
        self.num_relation = num_relation
        self.num_entity = num_entity

        self.mlp_w = tf.compat.v1.get_variable(
                name='mlp_w',
                shape=[self.num_relation * 2 + 1, self.embedding_dim],
                initializer=tf.compat.v1.keras.initializers.VarianceScaling(scale=1.0, mode="fan_avg", distribution=("uniform" if False else "truncated_normal"))
            )

        self.att_w = tf.compat.v1.get_variable(
                name='att_w',
                shape=[self.embedding_dim * 2, self.embedding_dim * 2],
                initializer=tf.compat.v1.keras.initializers.VarianceScaling(scale=1.0, mode="fan_avg", distribution=("uniform" if False else "truncated_normal"))
            )

        self.att_v = tf.compat.v1.get_variable(
                name='att_v',
                shape=[self.embedding_dim * 2],
                initializer=tf.compat.v1.keras.initializers.VarianceScaling(scale=1.0, mode="fan_avg", distribution=("uniform" if False else "truncated_normal")))

        self.att_b = tf.compat.v1.get_variable(
                name='att_b',
                shape=[self.embedding_dim * 2],
                initializer=tf.compat.v1.keras.initializers.VarianceScaling(scale=1.0, mode="fan_avg", distribution=("uniform" if False else "truncated_normal")))

        self.query_relation_embedding = tf.compat.v1.get_variable(
                name='query_relation_embedding',
                shape=[self.num_relation * 2, self.embedding_dim],
                initializer=tf.compat.v1.keras.initializers.VarianceScaling(scale=1.0, mode="fan_avg", distribution=("uniform" if False else "truncated_normal"))
        )

        self.l2_regularization = tf.nn.l2_loss(self.att_w) \
                                + tf.nn.l2_loss(self.mlp_w) \
                                + tf.nn.l2_loss(self.query_relation_embedding) \
                                + tf.nn.l2_loss(self.att_v)
                                # + tf.nn.l2_loss(self.att_b) \

        self.mask_emb = tf.concat([tf.ones([self.num_entity, 1]), tf.zeros([1, 1])], 0)
        self.mask_weight = tf.concat([tf.zeros([self.num_entity, 1]), tf.ones([1, 1])*1e19], 0)

    def _projection(self, e, n):
        norm = tf.nn.l2_normalize(n, 2)
        return e - tf.reduce_sum(input_tensor=e * norm, axis=2, keepdims = True) * norm

    def mlp(self, query, input, max_len):
        # query = tf.reshape(query, [-1, 1, self.embedding_dim])
        # query = tf.tile(query, [1, max_len, 1])

        hidden = tf.concat([query, input], 2)
        hidden = tf.reshape(hidden, [-1, self.embedding_dim * 2])
        hidden = tf.tanh(tf.matmul(hidden, self.att_w))
        hidden = tf.reshape(hidden, [-1, max_len, self.embedding_dim * 2])
        attention_logit = tf.reduce_sum(input_tensor=hidden * self.att_v, axis=2)
        return attention_logit

    def __call__(self, input, neighbor, query_relation_id, weight):
        input_shape = input.shape
        max_len = input_shape[1].value
        hidden_size = input_shape[2].value

        input_relation = neighbor[:, :, 0]
        input_entity = neighbor[:, :, 1]

        # [batch, len, emb] -> [batch * len, emb]
        projection = tf.nn.embedding_lookup(params=self.mlp_w, ids=input_relation)
        projection = self._projection(input, projection)
        mask = tf.nn.embedding_lookup(params=self.mask_emb, ids=input_entity)
        projection = projection * mask

        # query: [batch, emb]
        query_relation = tf.nn.embedding_lookup(params=self.query_relation_embedding, ids=query_relation_id)
        query_relation = tf.reshape(query_relation, [-1, 1, self.embedding_dim])
        query_relation = tf.tile(query_relation, [1, max_len, 1])

        # attention weight
        attention_logit = self.mlp(query_relation, projection, max_len)
        mask_logit = tf.nn.embedding_lookup(params=self.mask_weight, ids=input_entity)
        attention_logit -= tf.reshape(mask_logit, [-1, max_len])
        attention_weight = tf.nn.softmax(attention_logit)
        attention_weight += weight[:, :, 0] / (weight[:, :, 1] + 1)

        # output
        attention_weight = tf.reshape(attention_weight, [-1, max_len, 1])
        output = tf.reduce_sum(input_tensor=projection * attention_weight, axis=1)
        attention_weight = tf.reshape(attention_weight, [-1, max_len])
        return output, attention_weight

