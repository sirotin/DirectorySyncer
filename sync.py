# --------------------------------------------------------------------
# Directory syncer by Alexander Sirotin (c) 2016
# Originally created for syncing between home NAS backup and Amazon cloud
# Both are mounted on the host machine (Amazon cloud is mounted using acd_cli)
# This program comes without any warranty, use it at your own risk.
# Feel free to contact me at sirotin@gmail.com
# --------------------------------------------------------------------

import os
import sys
import filecmp
import logging
import argparse
import shutil

class DirectorySyncer:
	# Note: Recursive function, goes over all the sub-directories as well
	def __compareTwoDirectories(self, left, right):
		logging.debug("Comparing between '%s' and '%s'" % (left, right))

		# Make sure both directories exists
		if not os.path.exists(left) or not os.path.isdir(left):
			raise Exception, "Provided left directory '%s' does not exist or not a directory!" % left
		
		if not os.path.exists(right) or not os.path.isdir(right):
			raise Exception, "Provided right directory '%s' does not exist or not a directory!" % right

		# Compare the two directories and create two lists containing the missing parts
		result = filecmp.dircmp(left, right)
		leftOnly = self.__removeSpecial(result.left_only)
		rightOnly = self.__removeSpecial(result.right_only)

		# Add full path to the elements
		leftOnly = self.__convertToFullPath(left, leftOnly)
		rightOnly = self.__convertToFullPath(right, rightOnly)

		# Go over all the files and make sure that their sizes match
		commonFiles = self.__removeSpecial(result.common_files)
		for file in commonFiles:
			leftPath = os.path.join(left, file)
			leftFileSize = os.path.getsize(leftPath)

			rightPath = os.path.join(right, file)
			rightFileSize = os.path.getsize(rightPath)

			if leftFileSize > rightFileSize:
				logging.warn("Problem found: Size of '%s' (%s) is bigger than '%s' (%s)" % (leftPath, self.__formatDiskSpace(leftFileSize), rightPath, self.__formatDiskSpace(rightFileSize)))
				leftOnly.append(leftPath)
			elif rightFileSize > leftFileSize:
				logging.warn("Problem found: Size of '%s' (%s) is bigger than '%s' (%s)" % (rightPath, self.__formatDiskSpace(rightFileSize), leftPath, self.__formatDiskSpace(leftFileSize)))
				rightOnly.append(rightPath)

		# Get common dirs for recursive call
		dirs = self.__removeSpecial(result.common_dirs)
		for dir in dirs:
			childLeftOnly, childRightOnly = self.__compareTwoDirectories(os.path.join(left, dir), os.path.join(right, dir))
			leftOnly.extend(childLeftOnly)
			rightOnly.extend(childRightOnly)
		
		return leftOnly, rightOnly

	def __removeSpecial(self, list):
		return [x for x in list if not x.startswith(".")]

	def __convertToFullPath(self, basePath, list):
		for i in range(len(list)):
			list[i] = os.path.join(basePath, list[i])
		return list

	def __removeRootLocation(self, path, list):
		n = len(path) + 1
		for i in range(len(list)):
			list[i] = list[i][n:]
		return list

	def __getSizeStr(self, path):
		size = os.path.getsize(path)
		if (os.path.isdir(path)):
			size += self.__calculateDiskSpace(path, os.listdir(path))

		return self.__formatDiskSpace(size)

	def __calculateDiskSpace(self, path, list):
		diskSpace = 0
		for x in list:
			fullX = os.path.join(path, x)
			diskSpace += os.path.getsize(fullX)
			if os.path.isdir(fullX):
				content = [os.path.join(fullX, f) for f in os.listdir(fullX)]
				diskSpace += self.__calculateDiskSpace(path, content)
		return diskSpace

	def __askYesNoQuestion(self, message):
		yes = set(["yes", "y", ""])
		no = set(["no", "n"])

		while True:
			sys.stdout.write("%s [Y/N] " % message)
			choice = raw_input().lower()
			if choice in yes:
				return True
			elif choice in no:
				return False
			else:
				print("Please response with a valid answer.")

	def __buildYesNoQuestion(self, fromPath, toPath, file):
		f = os.path.join(fromPath, file)
		t = os.path.join(toPath, file)
		return self.__askYesNoQuestion("Copy from '%s' to '%s' (%s) ? " % (f, t, self.__getSizeStr(f)))

	def __verboseSelectFromList(self, fromPath, toPath, list):
		return [x for x in list if self.__buildYesNoQuestion(fromPath, toPath, x)]

	# Note: Recursive function, enters each directory and copies each file seperately
	def __copyMissingFiles(self, fromPath, toPath, list, dryRun):
		for file in list:
			src = os.path.join(fromPath, file)
			dst = os.path.join(toPath, file)

			# In case destination file exists, remove it...
			if (not dryRun) and os.path.exists(dst):
				os.remove(dst)

			try:
				if os.path.isdir(src):
					# Create the destination directory
					if not dryRun:
						os.mkdir(dst)

					# Recursive call to copy all directory content
					recursiveList = os.listdir(src)
					self.__copyMissingFiles(src, dst, recursiveList, dryRun)
				else:
					logging.info("Copying '%s' to '%s' (%s)" % (src, dst, self.__getSizeStr(src)))
					if not dryRun:
						shutil.copy(src, dst)
			except Exception as e:
				# In case of exception, we want to remove dst in order to avoid partially copied files
				if not dryRun:
					if os.path.isdir(dst):
						shutil.rmtree(dst)
					else:
						os.remove(dst)
				raise e

	def __formatDiskSpace(self, space):
		KB = 1024.0
		MB = 1024 * KB
		GB = 1024 * MB

		if space < 10 * MB:
			return "%.2f KB" % (space / KB)
		if (space < GB):
			return "%.2f MB" % (space / MB)

		return "%.2f GB" % (space / GB)

	def __showNeededDiskSpace(self, pointA, pointB, leftOnly, rightOnly):
		logging.info("Needed disk space for sync point '%s' is %s" % (pointA, self.__formatDiskSpace(self.__calculateDiskSpace(pointB, rightOnly))))
		logging.info("Needed disk space for sync point '%s' is %s" % (pointB, self.__formatDiskSpace(self.__calculateDiskSpace(pointA, leftOnly))))

	def sync(self, pointA, pointB, dryRun=False, verbose=False):
		if dryRun:
			logging.warn("DRY-RUN - No actual copies will occur !!!")

		logging.info("Syncing between '%s' and '%s'" % (pointA, pointB))

		try:
			# Create two lists contains the differences between the given points
			leftOnly, rightOnly = self.__compareTwoDirectories(pointA, pointB)
			leftOnlyLen = len(leftOnly)
			rightOnlyLen = len(rightOnly)
			logging.info("Found %d differences (%d are missing in '%s' and %d are missing in '%s')" % (leftOnlyLen + rightOnlyLen, rightOnlyLen, pointA, leftOnlyLen, pointB))

			# Remove base path from results
			leftOnly = self.__removeRootLocation(pointA, leftOnly)
			rightOnly = self.__removeRootLocation(pointB, rightOnly)

			# Show needed disk space
			self.__showNeededDiskSpace(pointA, pointB, leftOnly, rightOnly)

			# In case of verbose flag, ask the user what to do
			if (not dryRun) and verbose:
				leftOnly = self.__verboseSelectFromList(pointA, pointB, leftOnly)
				rightOnly = self.__verboseSelectFromList(pointB, pointA, rightOnly)

				# Show needed disk space
				self.__showNeededDiskSpace(pointA, pointB, leftOnly, rightOnly)

				# Recalculate number of differences
				leftOnlyLen = len(leftOnly)
				rightOnlyLen = len(rightOnly)
			
			logging.info("Start processing %d differences (%d are missing in '%s' and %d are missing in '%s')" % (leftOnlyLen + rightOnlyLen, rightOnlyLen, pointA, leftOnlyLen, pointB))
			self.__copyMissingFiles(pointA, pointB, leftOnly, dryRun)
			self.__copyMissingFiles(pointB, pointA, rightOnly, dryRun)
			logging.info("Done!")

		except Exception as e:
			logging.error(e.args[0])
			return False
		
		return True

def configure():
	# Configure the logger
	logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", datefmt="%d/%m/%Y %H:%M:%S", level=logging.INFO)

	# Read the command line arguments
	parser = argparse.ArgumentParser()
	parser.add_argument("-l", "--left", required=True)
	parser.add_argument("-r", "--right", required=True)
	parser.add_argument("-d", "--dry_run", action="store_const", const=True, default=False);
	parser.add_argument("-v", "--verbose", action="store_const", const=True, default=False);
	args = parser.parse_args()

	# Return the arguments
	return args

def main():
	args = configure()
	
	pointA = os.path.normpath(args.left)
	pointB = os.path.normpath(args.right)

	syncer = DirectorySyncer()
	syncer.sync(pointA, pointB, dryRun=args.dry_run, verbose=args.verbose)

if __name__ == "__main__":
	main()
