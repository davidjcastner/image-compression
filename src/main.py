from PIL import Image

TEST_IMAGE = './hue.png'
OUTPUT_IMAGE = './output.png'

# the test image is 768x512
# if saved as raw uncompressed data, the encoded image is 1,179,648 bytes
# test image is 701,970 bytes as a png, ~59.5% of original size

# bytes[0:2] = width
# bytes[2:4] = height
# each encoded channel

# skip the modes for now
# each row of the image is encoded im one of four modes
# 0b01 = row difference
# 0b10 = col difference
# 0b11 = row and col difference
# 0b00 = not used
# the next 3 bits say how many bits are used for the difference on that row

# each value of the channel starts with a 0 if the value does NOT use the difference
# otherwise it starts with a 1


Pixel = tuple[int, int, int]
PixelList = list[Pixel]

# assuming RGB for now


def encode_bits(value: int, length: int) -> list[bool]:
    '''encodes the given value into the given length with the most significant bit first'''
    bits = []
    for i in range(length):
        bits.append(bool(value & 1))
        value >>= 1
    bits.reverse()
    return bits


class BitArray:
    '''a class for storing a bit array'''

    def __init__(self, data: bytes = bytes()):
        self.data: bytes = data
        self.buffer: list[bool] = [False] * 8
        self.index: int = 0

    def reset_buffer(self):
        '''resets the buffer'''
        self.buffer = [False] * 8
        self.index = 0

    def add_bits(self, bits: list[bool]):
        '''adds bits to the buffer,
        if the buffer is full, it is written to the data'''
        for bit in bits:
            self.buffer[self.index] = bit
            self.index += 1
            if self.index == 8:
                self.data += bytes([
                    self.buffer[0] << 7
                    | self.buffer[1] << 6
                    | self.buffer[2] << 5
                    | self.buffer[3] << 4
                    | self.buffer[4] << 3
                    | self.buffer[5] << 2
                    | self.buffer[6] << 1
                    | self.buffer[7]])
                self.reset_buffer()

    def to_bytes(self):
        '''writes the remaining buffer to data and returns data'''
        if self.index > 0:
            self.data += bytes([
                self.buffer[0] << 7
                | self.buffer[1] << 6
                | self.buffer[2] << 5
                | self.buffer[3] << 4
                | self.buffer[4] << 3
                | self.buffer[5] << 2
                | self.buffer[6] << 1
                | self.buffer[7]])
            self.reset_buffer()
        return self.data

    def read_bits(self, index: int, length: int) -> int:
        '''reads bits from data starting at index for length,
        where index is the bit index in data'''
        mask = (1 << length) - 1
        start_index = index // 8
        end_index = (index + length + 7) // 8
        shift = (8 - (index + length)) % 8
        value = int.from_bytes(self.data[start_index: end_index], 'big')
        # print(value, shift, mask)
        value = value >> shift
        return value & mask


BITS_FOR_DIFF = 4
DIFF_VAL = BITS_FOR_DIFF - 1
DIFF_MOD = 1 << DIFF_VAL
MAX_DIFF = DIFF_MOD - 1
MIN_DIFF = -DIFF_MOD


def encode_image(width: int, height: int, pixels: PixelList) -> bytes:
    '''encodes the image with the given pixels'''
    encoded_bits = BitArray()
    encoded_bits.add_bits(encode_bits(width, 16))
    encoded_bits.add_bits(encode_bits(height, 16))

    # split the channels
    red = []
    green = []
    blue = []
    for pixel in pixels:
        red.append(pixel[0])
        green.append(pixel[1])
        blue.append(pixel[2])

    total_encoding = 3 * width * height
    step_size = total_encoding // 100
    step = 0
    encoding_index = 0

    # check if difference is between -8 and 7
    for channel in [red, green, blue]:
        # encode the channel
        current_value = 0
        for val in channel:
            delta = val - current_value
            current_value = val
            if delta < MIN_DIFF or delta > MAX_DIFF:
                encoded_bits.add_bits([False])
                encoded_bits.add_bits(encode_bits(val, 8))
            else:
                encoded_bits.add_bits([True])
                encoded_bits.add_bits([delta < 0])
                encoded_bits.add_bits(encode_bits(delta % DIFF_MOD, DIFF_VAL))

            encoding_index += 1
            if encoding_index % step_size == 0:
                step += 1
                print(f'{step}%')
    return encoded_bits.to_bytes()


def decode_image(data: bytes) -> tuple[int, int, PixelList]:
    '''decodes the image with the given pixels,
    returns the width, height, and the pixels'''
    bits = BitArray(data)
    width = bits.read_bits(0, 16)
    height = bits.read_bits(16, 16)
    pixel_count = width * height
    index = 32
    # print(f'width: {width}, height: {height}')
    # assert False

    def get_next_bits(n: int) -> int:
        '''returns the next n bits'''
        nonlocal index
        value = bits.read_bits(index, n)
        index += n
        return value

    red = []
    green = []
    blue = []

    total_decoding = 3 * width * height
    step_size = total_decoding // 100
    step = 0
    decoding_index = 0

    for channel in [red, green, blue]:
        value = 0
        for pixel_index in range(pixel_count):
            use_difference = bool(get_next_bits(1))
            if use_difference:
                negative = bool(get_next_bits(1))
                difference = get_next_bits(DIFF_VAL)
                if negative:
                    difference -= DIFF_MOD
                value += difference
            else:
                value = get_next_bits(8)
            channel.append(value)

            decoding_index += 1
            if decoding_index % step_size == 0:
                step += 1
                print(f'{step}%')

    return width, height, list(zip(red, green, blue))


def save_image(image_path: str, width: int, height: int, pixels: PixelList) -> None:
    '''saves the image to the given path'''
    image = Image.new('RGB', (width, height))
    image.putdata(pixels)
    image.save(image_path)


def is_same_image(pixels_a: PixelList, pixels_b: PixelList) -> bool:
    '''returns true if the two pixel lists are the same'''
    if len(pixels_a) != len(pixels_b):
        return False
    for i in range(len(pixels_a)):
        if pixels_a[i] != pixels_b[i]:
            return False
    return True


def save_compressed_image(name: str, data: bytes) -> None:
    '''saves the compressed image to the given path'''
    with open(f'{name}.bin', 'wb') as file:
        file.write(data)


def main():
    '''main function'''
    # load input image and output debugging information
    image = Image.open(TEST_IMAGE)
    input_width, input_height = image.size
    input_pixels = list(image.getdata())
    # print the input image size
    print(f'Input image size: {input_width}x{input_height}')

    # encode the image
    encoded_image = encode_image(input_width, input_height, input_pixels)

    # save the encoded image
    save_compressed_image('encoded', encoded_image)
    # print the size of the encoded image
    print(f'Encoded image size: {len(encoded_image)} bytes')

    # decode the image
    (output_width, output_height, output_pixels) = decode_image(encoded_image)
    # print the output image size
    print(f'Output image size: {output_width}x{output_height}')

    # save the decoded image
    save_image(OUTPUT_IMAGE, output_width, output_height, output_pixels)

    # test if the decoded image is the same as the input image
    assert is_same_image(input_pixels, output_pixels), 'Decoded image is not the same as the input image'


if __name__ == '__main__':
    main()
